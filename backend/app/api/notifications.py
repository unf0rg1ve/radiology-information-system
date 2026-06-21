from uuid import UUID
from datetime import timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.jwt import get_current_user
from app.models.user import User
from app.schemas.auth import UserMe
from app.models.audit_log import AuditLog
from app.models.order import Order, OrderStatus
from app.models.patient import Patient
from app.models.report import Report
from app.core.utils import utc_now

router = APIRouter(prefix="/notifications", tags=["Notifications"])


_STATUS_RU = {
    "NEW": "новое",
    "SCHEDULED": "назначено",
    "ARRIVED": "пациент прибыл",
    "IN_PROGRESS": "в обработке",
    "ACQUIRED": "снимки получены",
    "TO_REPORT": "на описание",
    "REPORTING": "описывается",
    "SIGNED": "подписано",
    "ISSUED": "выдано",
    "CANCELLED": "отменено",
}


@router.get("/cito")
async def get_cito_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user),
):
    """Список CITO-уведомлений за 7 дней."""
    seven_days_ago = utc_now() - timedelta(days=7)

    query = (
        select(AuditLog)
        .where(
            AuditLog.action == "CITO_NOTIFICATION",
            AuditLog.timestamp >= seven_days_ago,
        )
        .order_by(AuditLog.timestamp.desc())
    )

    if current_user.role == "REFERRER":
        result = await db.execute(
            select(Order).where(Order.referring_physician_id == current_user.id)
        )
        my_order_ids = [str(o.id) for o in result.scalars().all()]
        if not my_order_ids:
            return []
        cito_results = await db.execute(query)
        all_logs = cito_results.scalars().all()
        result_list = []
        for log in all_logs:
            if log.after_json and log.after_json.get("order_id") in my_order_ids:
                result_list.append({
                    "id": log.id,
                    "entity_id": str(log.entity_id) if log.entity_id else None,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "details": log.after_json,
                })
        return result_list

    result = await db.execute(query)
    return [
        {
            "id": log.id,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "details": log.after_json,
        }
        for log in result.scalars().all()
    ]


_NOTIFICATION_ACTIONS: dict[str, list[dict]] = {
    "REGISTRAR": [
        {"action": "CREATE", "entity_type": "Order", "label": "Новое направление"},
        {"action": "STATUS_UPDATE", "entity_type": "Order", "label": "Изменение статуса"},
    ],
    "TECHNOLOGIST": [
        {"action": "ARRIVED", "entity_type": "Order", "label": "Пациент прибыл"},
        {"action": "IN_PROGRESS", "entity_type": "Order", "label": "Начало обследования"},
    ],
    "RADIOLOGIST": [
        {"action": "UNMATCHED_RESOLVED", "entity_type": "UnmatchedStudy", "label": "Снимки прикреплены"},
        {"action": "SIGN", "entity_type": "Report", "label": "Заключение подписано"},
    ],
    "HEAD": [
        {"action": "UNMATCHED_RESOLVED", "entity_type": "UnmatchedStudy", "label": "Снимки прикреплены"},
        {"action": "SIGN", "entity_type": "Report", "label": "Заключение подписано"},
        {"action": "ISSUE", "entity_type": "Report", "label": "Заключение выдано"},
    ],
    "REFERRER": [
        {"action": "SIGN", "entity_type": "Report", "label": "Заключение подписано"},
        {"action": "ISSUE", "entity_type": "Report", "label": "Заключение выдано"},
        {"action": "CITO_NOTIFICATION", "entity_type": None, "label": "CITO: критическая находка"},
    ],
    "ADMIN": [
        {"action": "CREATE", "entity_type": "Order", "label": "Новое направление"},
        {"action": "STATUS_UPDATE", "entity_type": "Order", "label": "Изменение статуса"},
        {"action": "UNMATCHED_RESOLVED", "entity_type": "UnmatchedStudy", "label": "Снимки прикреплены"},
        {"action": "SIGN", "entity_type": "Report", "label": "Заключение подписано"},
        {"action": "ISSUE", "entity_type": "Report", "label": "Заключение выдано"},
        {"action": "CITO_NOTIFICATION", "entity_type": None, "label": "CITO: критическая находка"},
    ],
}


def _build_detail(log: AuditLog, rule_label: str) -> str:
    """Build a rich human-readable notification detail string from AuditLog after_json."""
    data = log.after_json or {}
    patient = data.get("patient_name", "")
    an = data.get("accession_number", "")
    service = data.get("service_name", "")
    modality = data.get("modality", "")
    body_part = data.get("body_part", "")

    patient_str = patient or "Неизвестный пациент"
    an_str = f" ({an})" if an else ""
    mod_str = f" {modality}" if modality else ""
    part_str = f", {body_part}" if body_part else ""
    svc_str = f" — {service}" if service else ""

    if log.action == "CREATE" and log.entity_type == "Order":
        return f"Направление{an_str} для {patient_str}{svc_str}{mod_str}{part_str}"

    if log.action == "ARRIVED" and log.entity_type == "Order":
        return f"Пациент {patient_str}{an_str} прибыл"

    if log.action == "IN_PROGRESS" and log.entity_type == "Order":
        return f"Пациент {patient_str}{an_str} — начало обследования"

    if log.action == "STATUS_UPDATE" and log.entity_type == "Order":
        new_status = data.get("status", "")
        status_ru = _STATUS_RU.get(new_status, new_status)
        cancelled = data.get("cancelled_reason")
        msg = f"Пациент {patient_str}{an_str} — статус: {status_ru}"
        if cancelled:
            msg += f" (причина: {cancelled})"
        return msg

    if log.action == "UNMATCHED_RESOLVED" and log.entity_type == "UnmatchedStudy":
        mod = data.get("modality", "")
        study_date = data.get("study_date", "")
        dicom_name = data.get("patient_name_dicom", "")
        name_note = f" (DICOM: {dicom_name})" if dicom_name and dicom_name != patient else ""
        date_note = f", дата {study_date}" if study_date else ""
        return f"Снимки{mod_str}{date_note} привязаны к {patient_str}{an_str}{svc_str}{name_note}"

    if log.action == "SIGN" and log.entity_type == "Report":
        ver = data.get("version", "")
        ver_str = f" v{ver}" if ver else ""
        rad = data.get("radiologist_name", "")
        rad_str = f" — {rad}" if rad else ""
        return f"Заключение{ver_str} по {patient_str}{an_str} подписано{rad_str}"

    if log.action == "ISSUE" and log.entity_type == "Report":
        ver = data.get("version", "")
        ver_str = f" v{ver}" if ver else ""
        ref = data.get("referring_physician_name", "")
        ref_str = f" → {ref}" if ref else ""
        return f"Заключение{ver_str} по {patient_str}{an_str} выдано{ref_str}"

    if log.action == "CITO_NOTIFICATION":
        rad = data.get("radiologist_name", "")
        rad_str = f" ({rad})" if rad else ""
        return f"CITO: {patient_str}{an_str} — критическая находка!{rad_str}"

    if log.action == "CREATE" and log.entity_type == "Patient":
        iin = data.get("iin", "")
        gender = data.get("gender", "")
        gender_str = f", {gender}" if gender else ""
        iin_str = f", ИИН {iin}" if iin else ""
        return f"Зарегистрирован новый пациент: {patient_str}{gender_str}{iin_str}"

    return rule_label


@router.get("/list")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user),
):
    """Получить уведомления для текущего пользователя по его роли."""
    rules = _NOTIFICATION_ACTIONS.get(current_user.role, [])
    if not rules:
        return []

    three_days_ago = utc_now() - timedelta(days=3)

    user_result = await db.execute(select(User).where(User.id == current_user.id))
    user = user_result.scalar_one_or_none()
    cleared_at = user.notifications_cleared_at if user else None

    conditions = []
    for rule in rules:
        cond = AuditLog.action == rule["action"]
        if rule["entity_type"]:
            cond = cond & (AuditLog.entity_type == rule["entity_type"])
        conditions.append(cond)

    filters = [AuditLog.timestamp >= three_days_ago, or_(*conditions)]
    if cleared_at:
        filters.append(AuditLog.timestamp > cleared_at)

    query = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.timestamp.desc())
        .limit(50)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    label_map = {}
    for rule in rules:
        key = (rule["action"], rule["entity_type"])
        label_map[key] = rule["label"]

    notifications = []
    for log in logs:
        key = (log.action, log.entity_type)
        label = label_map.get(key, log.action)

        detail = _build_detail(log, label)

        order_id = None
        link = None
        patient_name = None
        accession_number = None

        if log.entity_type == "Order" and log.entity_id:
            order_id = str(log.entity_id)
            link = "/worklist"
        elif log.entity_type == "UnmatchedStudy" and log.after_json:
            order_id = str(log.after_json.get("order_id", "")) if log.after_json.get("order_id") else None
            link = "/worklist"
        elif log.entity_type == "Report" and log.after_json:
            order_id = str(log.after_json.get("order_id", "")) if log.after_json.get("order_id") else None
            link = "/reports"
        elif log.entity_type == "Patient":
            link = "/patients"

        if log.after_json:
            patient_name = log.after_json.get("patient_name")
            accession_number = log.after_json.get("accession_number")

        notifications.append({
            "id": str(log.id),
            "action": log.action,
            "label": label,
            "detail": detail,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "order_id": order_id,
            "accession_number": accession_number,
            "patient_name": patient_name,
            "link": link,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        })

    return notifications


@router.post("/clear")
async def clear_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(get_current_user),
):
    """Сбросить уведомления — запомнить время очистки."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.notifications_cleared_at = utc_now()
        await db.commit()
    return {"ok": True}


def _format_patient_initials(patient) -> str:
    initials = patient.first_name[0] + "." if patient.first_name else ""
    if patient.middle_name:
        initials += patient.middle_name[0] + "."
    return f"{patient.last_name} {initials}".strip() if patient.last_name else initials
