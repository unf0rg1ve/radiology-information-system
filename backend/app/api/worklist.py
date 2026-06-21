from uuid import UUID
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.auth.rbac import technologist_only, any_authenticated, require_roles, Role
from app.schemas.auth import UserMe
from app.schemas.order import OrderResponse
from app.models.order import Order, OrderStatus
from app.models.appointment import Appointment
from app.models.study import Study
from app.models.unmatched_study import UnmatchedStudy
from app.models.audit_log import AuditLog
from app.services.orthanc_sync import sync_orthanc_studies
from app.services.ws_manager import ws_manager
from app.core.utils import utc_now
from app.services.audit import json_safe
from app.services.status_machine import validate_status_transition, InvalidStatusTransition

router = APIRouter(prefix="/worklist", tags=["Worklist"])


def _format_patient_initials(patient) -> str:
    initials = patient.first_name[0] + "." if patient.first_name else ""
    if patient.middle_name:
        initials += patient.middle_name[0] + "."
    return f"{patient.last_name} {initials}".strip() if patient.last_name else initials


class ResolveRequest(BaseModel):
    order_id: UUID


WORKLIST_DEFAULT_STATUSES = {
    Role.REGISTRAR.value: {OrderStatus.SCHEDULED, OrderStatus.ARRIVED},
    Role.TECHNOLOGIST.value: {OrderStatus.SCHEDULED, OrderStatus.ARRIVED, OrderStatus.IN_PROGRESS, OrderStatus.ACQUIRED},
    Role.RADIOLOGIST.value: {OrderStatus.TO_REPORT, OrderStatus.REPORTING},
    Role.HEAD.value: {OrderStatus.TO_REPORT, OrderStatus.REPORTING, OrderStatus.SIGNED},
    Role.REFERRER.value: {OrderStatus.SIGNED, OrderStatus.ISSUED},
}


def _order_response(order: Order) -> OrderResponse:
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


def _parse_order_status(status: str) -> OrderStatus:
    try:
        return OrderStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Неизвестный статус направления") from exc


async def _transition_order(
    db: AsyncSession,
    order: Order,
    target_status: OrderStatus,
    current_user: UserMe,
    action: str,
) -> None:
    before_status = _parse_order_status(order.status)
    try:
        validate_status_transition(before_status, target_status)
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    order.status = target_status
    if target_status == OrderStatus.ARRIVED:
        order.arrived_at = utc_now()
    audit = AuditLog(
        entity_type="Order",
        entity_id=order.id,
        action=action,
        user_id=current_user.id,
        before_json=json_safe({"status": before_status.value}),
        after_json=json_safe({
            "status": target_status.value,
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
    await ws_manager.broadcast("worklist", {
        "type": "status_changed",
        "order_id": str(order.id),
        "accession_number": order.accession_number,
        "status": target_status.value,
    })


@router.get("", response_model=list[OrderResponse])
async def get_worklist(
    device_id: UUID = Query(None),
    status: str = Query(None),
    priority: str = Query(None),
    date_from: date = Query(None),
    date_to: date = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    priority_order = case(
        (Order.priority == "URGENT", 0),
        (Order.priority == "ROUTINE", 1),
        else_=2,
    )
    query = select(Order).order_by(priority_order, Order.created_at.asc())

    if status:
        query = query.where(Order.status == _parse_order_status(status))
    elif current_user.role != Role.ADMIN.value:
        allowed_statuses = WORKLIST_DEFAULT_STATUSES.get(current_user.role)
        if allowed_statuses:
            query = query.where(Order.status.in_(allowed_statuses))
        else:
            return []

    if device_id:
        query = query.join(Appointment, Order.id == Appointment.order_id).where(
            Appointment.device_id == device_id
        )
    if priority:
        query = query.where(Order.priority == priority)
    if date_from:
        query = query.where(func.date(Order.created_at) >= date_from)
    if date_to:
        query = query.where(func.date(Order.created_at) <= date_to)

    result = await db.execute(query)
    orders = result.scalars().all()

    return [_order_response(order) for order in orders]


@router.get("/unmatched")
async def get_unmatched_studies(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([
        Role.TECHNOLOGIST.value,
        Role.RADIOLOGIST.value,
        Role.ADMIN.value,
    ])),
):
    """Несопоставленные студии — очередь для ручного сопоставления (ТЗ F4.5)."""
    await sync_orthanc_studies(db)

    result = await db.execute(
        select(UnmatchedStudy)
        .where(UnmatchedStudy.resolved == "N")
        .order_by(UnmatchedStudy.created_at.desc())
    )
    unmatched_studies = result.scalars().all()

    return [
        {
            "id": str(us.id),
            "study_instance_uid": us.study_instance_uid,
            "accession_number": us.accession_number,
            "orthanc_study_id": us.orthanc_study_id,
            "patient_id_dicom": us.patient_id_dicom or (us.raw_payload or {}).get("patient_id_dicom"),
            "patient_name_dicom": us.patient_name_dicom or (us.raw_payload or {}).get("patient_name_dicom"),
            "modality": us.modality or (us.raw_payload or {}).get("modality"),
            "study_date": us.study_date or (us.raw_payload or {}).get("study_date"),
            "created_at": us.created_at.isoformat() if us.created_at else None,
        }
        for us in unmatched_studies
    ]


@router.post("/unmatched/{unmatched_id}/resolve")
async def resolve_unmatched_study(
    unmatched_id: UUID,
    data: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([
        Role.TECHNOLOGIST.value,
        Role.RADIOLOGIST.value,
        Role.ADMIN.value,
    ])),
):
    """Привязать несопоставленную студию к заказу вручную (ТЗ F4.5)."""
    result = await db.execute(
        select(UnmatchedStudy).where(UnmatchedStudy.id == unmatched_id)
    )
    unmatched = result.scalar_one_or_none()
    if not unmatched:
        raise HTTPException(status_code=404, detail="Несопоставленная студия не найдена")

    if unmatched.resolved == "Y":
        raise HTTPException(status_code=409, detail="Студия уже привязана")

    order_result = await db.execute(select(Order).where(Order.id == data.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    if order.status not in (
        OrderStatus.NEW,
        OrderStatus.SCHEDULED,
        OrderStatus.ARRIVED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.ACQUIRED,
    ):
        raise HTTPException(
            status_code=422,
            detail="Привязать снимки можно только к направлению до этапа описания",
        )

    order.status = OrderStatus.ACQUIRED

    study_result = await db.execute(
        select(Study).where(Study.order_id == order.id)
    )
    study = study_result.scalar_one_or_none()
    if study:
        study.study_instance_uid = unmatched.study_instance_uid
        study.orthanc_study_id = unmatched.orthanc_study_id
        study.acquired_at = utc_now()
    else:
        study = Study(
            order_id=order.id,
            study_instance_uid=unmatched.study_instance_uid,
            orthanc_study_id=unmatched.orthanc_study_id,
            acquired_at=utc_now(),
        )
        db.add(study)

    unmatched.resolved = "Y"
    unmatched.resolved_order_id = order.id

    audit = AuditLog(
        entity_type="UnmatchedStudy",
        entity_id=unmatched.id,
        action="UNMATCHED_RESOLVED",
        user_id=current_user.id,
        after_json=json_safe({
            "unmatched_study_id": str(unmatched.id),
            "order_id": str(order.id),
            "study_instance_uid": unmatched.study_instance_uid,
            "accession_number": order.accession_number,
            "patient_name": _format_patient_initials(order.patient) if order.patient else None,
            "modality": unmatched.modality,
            "study_date": unmatched.study_date,
            "patient_name_dicom": unmatched.patient_name_dicom,
            "service_name": order.service.name_ru if order.service else None,
            "body_part": order.body_part,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)

    await db.flush()

    await ws_manager.broadcast("worklist", {
        "type": "unmatched_resolved",
        "order_id": str(order.id),
        "accession_number": order.accession_number,
        "status": order.status,
        "study_instance_uid": unmatched.study_instance_uid,
    })

    return {
        "status": "resolved",
        "order_id": str(order.id),
        "order_status": order.status,
        "study_instance_uid": unmatched.study_instance_uid,
    }


@router.post("/{order_id}/arrived")
async def mark_arrived(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(require_roles([Role.TECHNOLOGIST.value, Role.REGISTRAR.value, Role.ADMIN.value])),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    await _transition_order(db, order, OrderStatus.ARRIVED, current_user, "ARRIVED")
    return {"status": OrderStatus.ARRIVED.value, "timestamp": utc_now().isoformat()}


@router.post("/{order_id}/in-progress")
async def mark_in_progress(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(technologist_only),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    await _transition_order(db, order, OrderStatus.IN_PROGRESS, current_user, "IN_PROGRESS")
    return {"status": OrderStatus.IN_PROGRESS.value, "timestamp": utc_now().isoformat()}


@router.post("/{order_id}/qc")
async def quality_control(
    order_id: UUID,
    status: str = Query(..., pattern="^(ACCEPTED|RETAKE)$"),
    comment: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(technologist_only),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    study_result = await db.execute(select(Study).where(Study.order_id == order_id))
    study = study_result.scalar_one_or_none()
    if not study:
        study = Study(order_id=order_id, technologist_id=current_user.id)
        db.add(study)

    study.qc_status = status
    study.qc_attempts = study.qc_attempts or []
    study.qc_attempts.append({
        "status": status,
        "comment": comment,
        "timestamp": utc_now().isoformat(),
        "technologist_id": str(current_user.id),
    })

    if status == "ACCEPTED":
        order.status = OrderStatus.TO_REPORT
    elif status == "RETAKE":
        order.status = OrderStatus.IN_PROGRESS

    await db.flush()
    await ws_manager.broadcast("worklist", {
        "type": "status_changed",
        "order_id": str(order.id),
        "accession_number": order.accession_number,
        "status": order.status.value,
        "qc_status": status,
    })
    return {"status": order.status.value, "qc_status": status, "timestamp": utc_now().isoformat()}


class RetakeRequest(BaseModel):
    comment: str | None = None


@router.post("/{order_id}/retake")
async def retake_study(
    order_id: UUID,
    data: RetakeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(technologist_only),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    if order.status not in (OrderStatus.ACQUIRED, OrderStatus.TO_REPORT):
        raise HTTPException(
            status_code=422,
            detail=f"Пересъёмка невозможна в статусе «{order.status.value}». Доступно только в статусах ACQUIRED и TO_REPORT.",
        )

    study_result = await db.execute(select(Study).where(Study.order_id == order_id))
    study = study_result.scalar_one_or_none()
    if not study:
        study = Study(order_id=order_id, technologist_id=current_user.id)
        db.add(study)

    study.qc_status = "RETAKE"
    study.qc_attempts = study.qc_attempts or []
    study.qc_attempts.append({
        "status": "RETAKE",
        "comment": data.comment or "Снимок забракован лаборантом",
        "timestamp": utc_now().isoformat(),
        "technologist_id": str(current_user.id),
    })

    old_status = order.status
    order.status = OrderStatus.IN_PROGRESS

    audit = AuditLog(
        entity_type="Study",
        entity_id=study.id,
        action="RETAKE",
        user_id=current_user.id,
        before_json=json_safe({"order_status": old_status.value}),
        after_json=json_safe({
            "order_status": OrderStatus.IN_PROGRESS.value,
            "comment": data.comment,
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    await ws_manager.broadcast("worklist", {
        "type": "status_changed",
        "order_id": str(order.id),
        "accession_number": order.accession_number,
        "status": order.status.value,
        "qc_status": "RETAKE",
        "message": "Снимок забракован, требуется пересъёмка",
    })

    return {
        "status": order.status.value,
        "qc_status": "RETAKE",
        "message": "Снимок забракован. Сделайте новый снимок — он будет привязан к этому же направлению.",
        "timestamp": utc_now().isoformat(),
    }
