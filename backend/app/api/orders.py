from datetime import date

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select, func, or_
from sqlalchemy import Date
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import require_roles, Role, any_authenticated
from app.auth.jwt import get_current_user_optional
from app.schemas.auth import UserMe
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse, OrderStatusUpdate
from app.models.order import Order, OrderStatus
from app.models.patient import Patient
from app.models.service import Service
from app.models.study import Study
from app.models.diagnosis_icd import DiagnosisICD
from app.models.audit_log import AuditLog
from app.services.audit import json_safe
from app.services.pdf import generate_order_pdf
from app.services.org_utils import _get_org_data
from app.services.accession_number import generate_accession_number
from app.services.status_machine import validate_status_transition, InvalidStatusTransition
from app.services.orthanc_sync import resolve_study_for_order
from app.core.utils import utc_now

router = APIRouter(prefix="/orders", tags=["Orders"])


def _format_patient_initials(patient) -> str:
    initials = patient.first_name[0] + "." if patient.first_name else ""
    if patient.middle_name:
        initials += patient.middle_name[0] + "."
    return f"{patient.last_name} {initials}".strip() if patient.last_name else initials


def _order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        accession_number=order.accession_number,
        patient_id=order.patient_id,
        patient_name=_format_patient_initials(order.patient) if order.patient else None,
        patient_iin=order.patient.iin if order.patient else None,
        service_id=order.service_id,
        service_name=order.service.name_ru if order.service else None,
        modality=order.modality,
        body_part=order.body_part,
        priority=order.priority,
        financing_type=order.financing_type,
        referring_physician_id=order.referring_physician_id,
        referring_physician_name=order.referring_physician_name,
        diagnosis_icd_id=order.diagnosis_icd_id,
        diagnosis_icd_code=order.diagnosis_icd.code if order.diagnosis_icd else None,
        diagnosis_icd_name=order.diagnosis_icd.name_ru if order.diagnosis_icd else None,
        clinical_notes=order.clinical_notes,
        contrast_agent=order.contrast_agent,
        status=order.status,
        cancelled_reason=order.cancelled_reason,
        arrived_at=order.arrived_at,
        created_at=order.created_at,
        created_by=order.created_by,
    )


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: OrderStatus = Query(None),
    patient_id: UUID = Query(None),
    search: str = Query(None),
    modality: str = Query(None),
    date_from: date = Query(None),
    date_to: date = Query(None),
    sort_by: str = Query(None),
    sort_dir: str = Query("asc"),
    without_study: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    sort_whitelist = {
        "accession_number": Order.accession_number,
        "priority": Order.priority,
        "status": Order.status,
        "created_at": Order.created_at,
    }
    if sort_by and sort_by in sort_whitelist:
        order_col = sort_whitelist[sort_by]
        order_fn = order_col.asc() if sort_dir == "asc" else order_col.desc()
        query = select(Order).order_by(order_fn)
    else:
        query = select(Order).order_by(Order.created_at.desc())

    if current_user.role == "REFERRER":
        query = query.where(
            or_(
                Order.referring_physician_id == current_user.id,
                Order.referring_physician_id == None,
            )
        )

    if status:
        query = query.where(Order.status == status)
    if patient_id:
        query = query.where(Order.patient_id == patient_id)
    if modality:
        query = query.where(Order.modality == modality.upper())
    if date_from:
        query = query.where(Order.created_at >= func.cast(date_from, Date))
    if date_to:
        query = query.where(Order.created_at <= func.cast(date_to, Date) + 1)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Patient, Order.patient_id == Patient.id).where(
            or_(
                Order.accession_number.ilike(term),
                Patient.iin.ilike(term),
                Patient.last_name.ilike(term),
                Patient.first_name.ilike(term),
                Patient.middle_name.ilike(term),
                func.concat(
                    Patient.last_name,
                    " ",
                    Patient.first_name,
                    " ",
                    func.coalesce(Patient.middle_name, ""),
                ).ilike(term),
            )
        )

    if without_study:
        query = query.outerjoin(Study, Study.order_id == Order.id).where(
            (Study.id == None) | (Study.orthanc_study_id == None)
        )

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    return [_order_to_response(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")
    return _order_to_response(order)


@router.post("", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([Role.REGISTRAR.value, Role.REFERRER.value, Role.HEAD.value, Role.ADMIN.value])),
):
    an = await generate_accession_number(db)

    order = Order(
        accession_number=an,
        patient_id=data.patient_id,
        service_id=data.service_id,
        modality=data.modality,
        body_part=data.body_part,
        priority=data.priority,
        financing_type=data.financing_type,
        referring_physician_id=data.referring_physician_id,
        referring_physician_name=data.referring_physician_name,
        diagnosis_icd_id=data.diagnosis_icd_id,
        clinical_notes=data.clinical_notes,
        contrast_agent=data.contrast_agent,
        status=OrderStatus.NEW,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order, ["patient", "service", "diagnosis_icd"])

    audit = AuditLog(
        entity_type="Order",
        entity_id=order.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe({
            "accession_number": order.accession_number,
            "patient_id": order.patient_id,
            "patient_name": _format_patient_initials(order.patient) if order.patient else None,
            "service_id": order.service_id,
            "service_name": order.service.name_ru if order.service else None,
            "modality": order.modality,
            "body_part": order.body_part,
            "priority": order.priority,
            "financing_type": order.financing_type,
            "status": order.status,
            "referring_physician_id": order.referring_physician_id,
            "referring_physician_name": order.referring_physician_name,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return _order_to_response(order)


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([Role.REGISTRAR.value, Role.HEAD.value, Role.ADMIN.value])),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    try:
        validate_status_transition(order.status, data.status)
    except InvalidStatusTransition as e:
        raise HTTPException(status_code=422, detail=str(e))

    old_status = order.status
    old_cancelled_reason = order.cancelled_reason
    order.status = data.status
    if data.status == OrderStatus.ARRIVED and order.arrived_at is None:
        order.arrived_at = utc_now()
    if data.status == OrderStatus.CANCELLED and data.reason:
        order.cancelled_reason = data.reason

    await db.flush()
    await db.refresh(order, ["patient", "service", "diagnosis_icd"])

    audit = AuditLog(
        entity_type="Order",
        entity_id=order.id,
        action="STATUS_UPDATE",
        user_id=current_user.id,
        before_json=json_safe({"status": old_status, "cancelled_reason": old_cancelled_reason}),
        after_json=json_safe({
            "status": order.status,
            "cancelled_reason": order.cancelled_reason,
            "accession_number": order.accession_number,
            "patient_name": _format_patient_initials(order.patient) if order.patient else None,
            "service_name": order.service.name_ru if order.service else None,
            "modality": order.modality,
            "body_part": order.body_part,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return _order_to_response(order)


@router.get("/{order_id}/study")
async def get_order_study(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    study = await resolve_study_for_order(db, order)
    if not study or not study.study_instance_uid:
        raise HTTPException(status_code=404, detail="Снимки ещё не получены")

    return {
        "study_instance_uid": study.study_instance_uid,
        "orthanc_study_id": study.orthanc_study_id,
    }


@router.get("/{order_id}/pdf")
async def get_order_pdf(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user_optional),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    org_data = await _get_org_data(db, order.org_id)

    order_data = {
        "accession_number": order.accession_number, "status": order.status,
        "priority": order.priority, "financing_type": order.financing_type,
        "modality": order.modality, "body_part": order.body_part,
        "clinical_notes": order.clinical_notes, "contrast_agent": order.contrast_agent,
        "created_at": order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "",
        "diagnosis_icd_code": order.diagnosis_icd.code if order.diagnosis_icd else None,
        "diagnosis_icd_name": order.diagnosis_icd.name_ru if order.diagnosis_icd else None,
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
        service_data = {"code_gombp": order.service.code_gombp, "name_ru": order.service.name_ru, "modality": order.service.modality, "tariff_paid": float(order.service.tariff_paid) if order.service.tariff_paid else 0}

    pdf_bytes = generate_order_pdf(order_data, patient_data, service_data, org_data)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="order_{order.accession_number}.pdf"'})


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([Role.REGISTRAR.value, Role.REFERRER.value, Role.HEAD.value, Role.ADMIN.value])),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    if order.status not in (OrderStatus.NEW, OrderStatus.SCHEDULED):
        raise HTTPException(
            status_code=422,
            detail=f"Редактирование недоступно для направлений в статусе '{order.status.value}'",
        )

    update_data = data.model_dump(exclude_unset=True)
    before_snapshot = json_safe({
        "service_id": str(order.service_id) if order.service_id else None,
        "modality": order.modality,
        "body_part": order.body_part,
        "priority": order.priority,
        "financing_type": order.financing_type,
        "referring_physician_id": str(order.referring_physician_id) if order.referring_physician_id else None,
        "referring_physician_name": order.referring_physician_name,
        "diagnosis_icd_id": str(order.diagnosis_icd_id) if order.diagnosis_icd_id else None,
        "clinical_notes": order.clinical_notes,
        "contrast_agent": order.contrast_agent,
    })

    for field, value in update_data.items():
        setattr(order, field, value)

    await db.flush()
    await db.refresh(order, ["patient", "service", "diagnosis_icd"])

    audit = AuditLog(
        entity_type="Order",
        entity_id=order.id,
        action="UPDATE",
        user_id=current_user.id,
        before_json=before_snapshot,
        after_json=json_safe(update_data),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return _order_to_response(order)


@router.delete("/{order_id}")
async def delete_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([Role.REGISTRAR.value, Role.HEAD.value, Role.ADMIN.value])),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    if order.status != OrderStatus.NEW:
        raise HTTPException(status_code=422, detail=f"Удаление недоступно для направлений в статусе '{order.status.value}'")

    if order.study or order.reports:
        raise HTTPException(status_code=409, detail="Невозможно удалить направление со связанными исследованиями или отчётами")

    before_snapshot = json_safe({
        "id": str(order.id),
        "accession_number": order.accession_number,
        "patient_id": str(order.patient_id) if order.patient_id else None,
        "service_id": str(order.service_id) if order.service_id else None,
        "modality": order.modality,
        "body_part": order.body_part,
        "priority": order.priority,
        "financing_type": order.financing_type,
        "status": order.status.value,
        "referring_physician_id": str(order.referring_physician_id) if order.referring_physician_id else None,
        "referring_physician_name": order.referring_physician_name,
        "diagnosis_icd_id": str(order.diagnosis_icd_id) if order.diagnosis_icd_id else None,
        "clinical_notes": order.clinical_notes,
        "contrast_agent": order.contrast_agent,
        "created_at": str(order.created_at) if order.created_at else None,
        "created_by": str(order.created_by) if order.created_by else None,
    })

    audit = AuditLog(
        entity_type="Order",
        entity_id=order.id,
        action="DELETE",
        user_id=current_user.id,
        before_json=before_snapshot,
        after_json=None,
        timestamp=utc_now(),
    )
    db.add(audit)

    await db.delete(order)
    await db.flush()

    return {"detail": "Направление удалено"}


@router.get("/{order_id}/history")
async def get_order_history(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    from app.models.user import User

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    query = (
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id, isouter=True)
        .where(AuditLog.entity_type == "Order", AuditLog.entity_id == order_id)
        .order_by(AuditLog.timestamp.desc())
    )
    rows = await db.execute(query)
    history = []
    for audit_log, user in rows.all():
        history.append({
            "action": audit_log.action,
            "timestamp": audit_log.timestamp,
            "user_id": str(audit_log.user_id) if audit_log.user_id else None,
            "user_name": f"{user.last_name} {user.first_name}" if user else None,
            "before_json": audit_log.before_json,
            "after_json": audit_log.after_json,
        })
    return history
