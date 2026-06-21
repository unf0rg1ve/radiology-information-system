from uuid import UUID
import hashlib
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select, or_, func
from sqlalchemy import Date
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import radiologist_only, any_authenticated, head_only
from app.auth.jwt import get_current_user, get_current_user_optional
from app.schemas.auth import UserMe
from app.schemas.report import ReportCreate, ReportResponse, ReportSignRequest
from app.models.report import Report
from app.models.order import Order, OrderStatus
from app.models.patient import Patient
from app.models.audit_log import AuditLog
from app.services.audit import json_safe
from app.services.status_machine import validate_status_transition
from app.services.pdf import generate_report_pdf
from app.services.org_utils import _get_org_data
from app.services.ws_manager import ws_manager
from app.core.utils import utc_now

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    order_id: UUID = None,
    status: str = None,
    search: str = Query(None),
    modality: str = Query(None),
    date_from: date = Query(None),
    date_to: date = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(Report).order_by(Report.created_at.desc())

    if order_id:
        query = query.where(Report.order_id == order_id)
    if status:
        query = query.where(Report.status == status)
    if modality:
        query = query.join(Report.order).where(Order.modality == modality.upper())
    if date_from:
        query = query.where(Report.created_at >= func.cast(date_from, Date))
    if date_to:
        query = query.where(Report.created_at <= func.cast(date_to, Date) + 1)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Report.order).join(Order.patient).where(
            or_(
                Patient.last_name.ilike(term),
                Patient.first_name.ilike(term),
                Patient.iin.ilike(term),
                func.concat(Patient.last_name, " ", Patient.first_name, " ", func.coalesce(Patient.middle_name, "")).ilike(term),
            )
        )

    if current_user.role == "REFERRER":
        query = query.join(Report.order).where(
            or_(
                Order.referring_physician_id == current_user.id,
                Order.referring_physician_id == None,
            )
        )

    result = await db.execute(query)
    reports = result.scalars().all()

    response = []
    for r in reports:
        initials = ""
        if r.order and r.order.patient:
            p = r.order.patient
            initials = p.first_name[0] + "." if p.first_name else ""
            initials += p.middle_name[0] + "." if p.middle_name else ""
            initials = f"{p.last_name} {initials}".strip()
        response.append(ReportResponse(
            id=r.id,
            order_id=r.order_id,
            accession_number=r.order.accession_number if r.order else None,
            patient_name=initials or None,
            service_name=r.order.service.name_ru if r.order and r.order.service else None,
            radiologist_id=r.radiologist_id,
            radiologist_name=f"{r.radiologist.last_name} {r.radiologist.first_name}" if r.radiologist else None,
            protocol_template_id=r.protocol_template_id,
            structured_fields=r.structured_fields,
            description_text=r.description_text,
            conclusion_text=r.conclusion_text,
            critical_finding=r.critical_finding,
            diagnosis_icd_codes=r.diagnosis_icd_codes,
            status=r.status,
            version=r.version,
            parent_report_id=r.parent_report_id,
            second_opinion_of_report_id=r.second_opinion_of_report_id,
            signed_at=r.signed_at,
            content_hash=r.content_hash,
            issued_at=r.issued_at,
            created_at=r.created_at,
        ))

    return response


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")

    if current_user.role == "REFERRER":
        order_result = await db.execute(select(Order).where(Order.id == report.order_id))
        order = order_result.scalar_one_or_none()
        if order and order.referring_physician_id not in (None, current_user.id):
            raise HTTPException(status_code=403, detail="Нет доступа к заключению")

    return ReportResponse(
        id=report.id,
        order_id=report.order_id,
        accession_number=report.order.accession_number if report.order else None,
        patient_name=f"{report.order.patient.last_name} {report.order.patient.first_name}" if report.order and report.order.patient else None,
        service_name=report.order.service.name_ru if report.order and report.order.service else None,
        radiologist_id=report.radiologist_id,
        radiologist_name=f"{report.radiologist.last_name} {report.radiologist.first_name}" if report.radiologist else None,
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status=report.status,
        version=report.version,
        parent_report_id=report.parent_report_id,
        second_opinion_of_report_id=report.second_opinion_of_report_id,
        signed_at=report.signed_at,
        content_hash=report.content_hash,
        issued_at=report.issued_at,
        created_at=report.created_at,
    )


@router.post("", response_model=ReportResponse)
async def create_report(
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(radiologist_only),
):
    report = Report(
        order_id=data.order_id,
        radiologist_id=current_user.id,
        protocol_template_id=data.protocol_template_id,
        structured_fields=data.structured_fields or {},
        description_text=data.description_text,
        conclusion_text=data.conclusion_text,
        critical_finding=data.critical_finding,
        diagnosis_icd_codes=data.diagnosis_icd_codes or [],
        status="DRAFT",
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    # Update order status
    order_result = await db.execute(select(Order).where(Order.id == data.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = OrderStatus.REPORTING
        await db.flush()

    audit = AuditLog(
        entity_type="Report",
        entity_id=report.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe({
            "order_id": report.order_id,
            "radiologist_id": report.radiologist_id,
            "protocol_template_id": report.protocol_template_id,
            "status": report.status,
            "version": report.version,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return ReportResponse(
        id=report.id,
        order_id=report.order_id,
        radiologist_id=report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status=report.status,
        version=report.version,
        created_at=report.created_at,
    )


@router.post("/{report_id}/new-version", response_model=ReportResponse)
async def new_report_version(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(radiologist_only),
):
    """Создать новую версию отчёта из SIGNED/ISSUED (Задача 4)."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")
    if report.status not in ("SIGNED", "ISSUED"):
        raise HTTPException(status_code=403, detail="Новая версия может быть создана только из подписанного или выданного заключения")
    if current_user.id != report.radiologist_id:
        raise HTTPException(status_code=403, detail="Создать новую версию может только автор заключения")

    next_version = str(int(report.version) + 1)

    new_report = Report(
        order_id=report.order_id,
        radiologist_id=current_user.id,
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status="DRAFT",
        version=next_version,
        parent_report_id=report.id,
    )
    db.add(new_report)

    # Если заказ был ISSUED — перевести в REPORTING
    order_result = await db.execute(select(Order).where(Order.id == report.order_id))
    order = order_result.scalar_one_or_none()
    if order and order.status == OrderStatus.ISSUED:
        validate_status_transition(order.status, OrderStatus.REPORTING)
        order.status = OrderStatus.REPORTING

    await db.flush()
    await db.refresh(new_report)

    audit = AuditLog(
        entity_type="Report",
        entity_id=new_report.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe({
            "order_id": new_report.order_id,
            "radiologist_id": new_report.radiologist_id,
            "parent_report_id": new_report.parent_report_id,
            "status": new_report.status,
            "version": new_report.version,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return ReportResponse(
        id=new_report.id,
        order_id=new_report.order_id,
        radiologist_id=new_report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=new_report.protocol_template_id,
        structured_fields=new_report.structured_fields,
        description_text=new_report.description_text,
        conclusion_text=new_report.conclusion_text,
        critical_finding=new_report.critical_finding,
        diagnosis_icd_codes=new_report.diagnosis_icd_codes,
        status=new_report.status,
        version=new_report.version,
        parent_report_id=new_report.parent_report_id,
        created_at=new_report.created_at,
    )


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: UUID,
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(radiologist_only),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")
    if report.status != "DRAFT":
        raise HTTPException(status_code=403, detail="Редактирование подписанного документа запрещено")
    if current_user.id != report.radiologist_id:
        raise HTTPException(status_code=403, detail="Редактировать может только автор заключения")

    update_data = data.model_dump(exclude_unset=True)
    before = {field: json_safe(getattr(report, field)) for field in update_data}
    for field, value in update_data.items():
        setattr(report, field, value)
    after = {field: json_safe(getattr(report, field)) for field in update_data}

    await db.flush()
    await db.refresh(report)

    audit = AuditLog(
        entity_type="Report",
        entity_id=report.id,
        action="UPDATE",
        user_id=current_user.id,
        before_json=before,
        after_json=after,
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return ReportResponse(
        id=report.id,
        order_id=report.order_id,
        radiologist_id=report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status=report.status,
        version=report.version,
        created_at=report.created_at,
    )


@router.post("/{report_id}/sign", response_model=ReportResponse)
async def sign_report(
    report_id: UUID,
    data: ReportSignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(radiologist_only),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")
    if report.status != "DRAFT":
        raise HTTPException(status_code=403, detail="Документ уже подписан")
    if current_user.id != report.radiologist_id:
        raise HTTPException(status_code=403, detail="Подписать может только автор заключения")

    # Generate content hash (ЭЦП-ready: врач + timestamp + SHA-256)
    content = f"{report.conclusion_text or ''}|{report.description_text or ''}|{utc_now().isoformat()}|{current_user.id}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    report.status = "SIGNED"
    report.signed_at = utc_now()
    report.content_hash = content_hash

    # Update order status
    order_result = await db.execute(select(Order).where(Order.id == report.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = OrderStatus.SIGNED
        await db.flush()

    audit = AuditLog(
        entity_type="Report",
        entity_id=report.id,
        action="SIGN",
        user_id=current_user.id,
        after_json=json_safe({
            "status": report.status,
            "signed_at": report.signed_at,
            "content_hash": report.content_hash,
            "version": report.version,
            "order_id": str(order.id) if order else None,
            "accession_number": order.accession_number if order else None,
            "patient_name": f"{order.patient.last_name} {order.patient.first_name[0]}.{' ' + order.patient.middle_name[0] + '.' if order.patient and order.patient.middle_name else ''}" if order and order.patient else None,
            "service_name": order.service.name_ru if order and order.service else None,
            "modality": order.modality if order else None,
            "body_part": order.body_part if order else None,
            "referring_physician_name": order.referring_physician_name if order else None,
            "radiologist_name": f"{current_user.last_name} {current_user.first_name}",
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    await db.flush()
    await db.refresh(report)

    return ReportResponse(
        id=report.id,
        order_id=report.order_id,
        radiologist_id=report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status=report.status,
        version=report.version,
        signed_at=report.signed_at,
        content_hash=report.content_hash,
        created_at=report.created_at,
    )


@router.post("/{report_id}/issue", response_model=ReportResponse)
async def issue_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(radiologist_only),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")
    if report.status != "SIGNED":
        raise HTTPException(status_code=403, detail="Документ должен быть подписан перед выдачей")

    report.status = "ISSUED"
    report.issued_at = utc_now()

    # Update order status
    order_result = await db.execute(select(Order).where(Order.id == report.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = OrderStatus.ISSUED

    await ws_manager.broadcast("worklist", {
        "type": "status_changed",
        "order_id": str(report.order_id),
        "accession_number": order.accession_number if order else None,
        "status": OrderStatus.ISSUED.value,
        "report_id": str(report.id),
    })

    # Audit issue action
    issue_audit = AuditLog(
        entity_type="Report",
        entity_id=report.id,
        action="ISSUE",
        user_id=current_user.id,
        after_json=json_safe({
            "status": report.status,
            "issued_at": report.issued_at,
            "version": report.version,
            "order_id": order.id if order else None,
            "accession_number": order.accession_number if order else None,
            "patient_name": f"{order.patient.last_name} {order.patient.first_name[0]}.{' ' + order.patient.middle_name[0] + '.' if order.patient and order.patient.middle_name else ''}" if order and order.patient else None,
            "service_name": order.service.name_ru if order and order.service else None,
            "modality": order.modality if order else None,
            "body_part": order.body_part if order else None,
            "referring_physician_name": order.referring_physician_name if order else None,
            "radiologist_name": f"{current_user.last_name} {current_user.first_name}",
        }),
        timestamp=utc_now(),
    )
    db.add(issue_audit)

    # CITO notification for critical findings
    if report.critical_finding and order:
        cito_log = AuditLog(
            action="CITO_NOTIFICATION",
            entity_type="report",
            entity_id=report.id,
            user_id=current_user.id,
            after_json=json_safe({
                "order_id": order.id,
                "referring_physician_id": order.referring_physician_id,
                "accession_number": order.accession_number,
                "patient_name": f"{order.patient.last_name} {order.patient.first_name[0]}.{' ' + order.patient.middle_name[0] + '.' if order.patient and order.patient.middle_name else ''}" if order and order.patient else None,
                "service_name": order.service.name_ru if order and order.service else None,
                "modality": order.modality if order else None,
                "body_part": order.body_part if order else None,
                "radiologist_name": f"{current_user.last_name} {current_user.first_name}",
            }),
            timestamp=utc_now(),
        )
        db.add(cito_log)
        await ws_manager.broadcast("cito", {
            "type": "cito_notification",
            "report_id": str(report.id),
            "order_id": str(order.id),
            "accession_number": order.accession_number,
            "referring_physician_id": str(order.referring_physician_id) if order.referring_physician_id else None,
            "message": "Критическая находка",
        })

    await db.flush()
    await db.refresh(report)

    return ReportResponse(
        id=report.id,
        order_id=report.order_id,
        radiologist_id=report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=report.protocol_template_id,
        structured_fields=report.structured_fields,
        description_text=report.description_text,
        conclusion_text=report.conclusion_text,
        critical_finding=report.critical_finding,
        diagnosis_icd_codes=report.diagnosis_icd_codes,
        status=report.status,
        version=report.version,
        signed_at=report.signed_at,
        content_hash=report.content_hash,
        issued_at=report.issued_at,
        created_at=report.created_at,
    )


@router.post("/{report_id}/second-opinion", response_model=ReportResponse)
async def create_second_opinion(
    report_id: UUID,
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(head_only),
):
    """Создать второе мнение / рецензию (F5.7).

    Инициирует заведующий. Оригинальный Report не перезаписывается.
    """
    if current_user.role == "ADMIN":
        raise HTTPException(status_code=403, detail="Администратор не может создавать вторые мнения")
    original_result = await db.execute(select(Report).where(Report.id == report_id))
    original = original_result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Оригинальное заключение не найдено")

    # Создаём новый Report как второе мнение
    new_report = Report(
        order_id=original.order_id,
        radiologist_id=current_user.id,
        protocol_template_id=data.protocol_template_id or original.protocol_template_id,
        structured_fields=data.structured_fields or original.structured_fields,
        description_text=data.description_text,
        conclusion_text=data.conclusion_text,
        critical_finding=data.critical_finding if data.critical_finding is not None else original.critical_finding,
        diagnosis_icd_codes=data.diagnosis_icd_codes or original.diagnosis_icd_codes,
        status="DRAFT",
        version="1",
        second_opinion_of_report_id=report_id,
    )
    db.add(new_report)
    await db.flush()
    await db.refresh(new_report)

    audit = AuditLog(
        entity_type="Report",
        entity_id=new_report.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe({
            "order_id": new_report.order_id,
            "radiologist_id": new_report.radiologist_id,
            "second_opinion_of_report_id": new_report.second_opinion_of_report_id,
            "status": new_report.status,
            "version": new_report.version,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return ReportResponse(
        id=new_report.id,
        order_id=new_report.order_id,
        radiologist_id=new_report.radiologist_id,
        radiologist_name=f"{current_user.last_name} {current_user.first_name}",
        protocol_template_id=new_report.protocol_template_id,
        structured_fields=new_report.structured_fields,
        description_text=new_report.description_text,
        conclusion_text=new_report.conclusion_text,
        critical_finding=new_report.critical_finding,
        diagnosis_icd_codes=new_report.diagnosis_icd_codes,
        status=new_report.status,
        version=new_report.version,
        second_opinion_of_report_id=new_report.second_opinion_of_report_id,
        created_at=new_report.created_at,
    )


@router.get("/{report_id}/pdf")
async def get_report_pdf(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user_optional),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Заключение не найдено")

    order_result = await db.execute(select(Order).where(Order.id == report.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    org_data = await _get_org_data(db, order.org_id)

    report_data = {
        "status": report.status, "description_text": report.description_text,
        "conclusion_text": report.conclusion_text, "critical_finding": report.critical_finding,
        "diagnosis_icd_codes": report.diagnosis_icd_codes, "content_hash": report.content_hash,
        "signed_at": report.signed_at.strftime("%d.%m.%Y %H:%M") if report.signed_at else None,
        "created_at": report.created_at.strftime("%d.%m.%Y %H:%M") if report.created_at else None,
        "version": report.version,
    }
    order_data = {
        "accession_number": order.accession_number, "priority": order.priority,
        "financing_type": order.financing_type, "modality": order.modality,
        "body_part": order.body_part, "clinical_notes": order.clinical_notes,
        "created_at": order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "",
        "referring_physician_name": order.referring_physician_name,
    }
    patient_data = {}
    if order.patient:
        patient_data = {
            "iin": order.patient.iin, "last_name": order.patient.last_name,
            "first_name": order.patient.first_name, "middle_name": order.patient.middle_name,
            "birth_date": order.patient.birth_date.strftime("%d.%m.%Y") if order.patient.birth_date else "",
            "gender": order.patient.gender,
        }
    service_data = {}
    if order.service:
        service_data = {"code_gombp": order.service.code_gombp, "name_ru": order.service.name_ru}
    radiologist_data = {}
    if report.radiologist:
        radiologist_data = {
            "last_name": report.radiologist.last_name, "first_name": report.radiologist.first_name,
            "middle_name": report.radiologist.middle_name, "specialization": report.radiologist.specialization,
            "license_number": report.radiologist.license_number,
        }

    pdf_bytes = generate_report_pdf(report_data, order_data, patient_data, service_data, radiologist_data, org_data)
    filename = f"report_{order.accession_number}_v{report.version}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
