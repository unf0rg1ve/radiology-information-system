import hmac
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import get_settings
from app.models.order import Order, OrderStatus
from app.models.study import Study
from app.models.unmatched_study import UnmatchedStudy
from app.services.ws_manager import ws_manager
from app.core.utils import utc_now

settings = get_settings()
router = APIRouter(prefix="/webhook", tags=["Webhook"])


class OrthancStoredPayload(BaseModel):
    study_instance_uid: str | None = None
    accession_number: str | None = None
    series_uid: str = ""
    sop_instance_uid: str = ""
    modality: str = ""
    patient_name: str = ""
    patient_id: str = ""
    orthanc_instance_id: str = ""


@router.post("/orthanc/stored")
async def orthanc_stored(
    payload: OrthancStoredPayload,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str = Header(None),
):
    """Webhook от Orthanc OnStoredInstance — новые снимки получены.

    Автосопоставление студии с заказом по AN / Study UID (F4.4).
    Статус → ACQUIRED автоматически, < 5 с после webhook (ТЗ F4.4).
    """
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    order = None

    # 1. Ищем заказ по Accession Number
    if payload.accession_number:
        result = await db.execute(
            select(Order).where(Order.accession_number == payload.accession_number)
        )
        order = result.scalar_one_or_none()

    # 2. Если не нашли по AN, ищем по Study UID через Study
    if not order and payload.study_instance_uid:
        study_result = await db.execute(
            select(Study).where(Study.study_instance_uid == payload.study_instance_uid)
        )
        study = study_result.scalar_one_or_none()
        if study:
            order_result = await db.execute(
                select(Order).where(Order.id == study.order_id)
            )
            order = order_result.scalar_one_or_none()

    if not order:
        existing = await db.execute(
            select(UnmatchedStudy).where(
                UnmatchedStudy.study_instance_uid == payload.study_instance_uid
            )
        )
        unmatched = existing.scalar_one_or_none()
        if unmatched:
            unmatched.raw_payload = payload.model_dump()
        else:
            unmatched = UnmatchedStudy(
                study_instance_uid=payload.study_instance_uid,
                accession_number=payload.accession_number,
                orthanc_study_id=payload.orthanc_instance_id,
                patient_id_dicom=payload.patient_id,
                patient_name_dicom=payload.patient_name,
                modality=payload.modality,
                raw_payload=payload.model_dump(),
                resolved="N",
            )
            db.add(unmatched)
        await db.flush()
        await ws_manager.broadcast("worklist", {
            "type": "unmatched_study",
            "accession_number": payload.accession_number,
            "study_instance_uid": payload.study_instance_uid,
            "modality": payload.modality,
        })
        return {
            "status": "unmatched",
            "message": "Study not matched to any order. Queued for manual matching.",
            "accession_number": payload.accession_number,
            "study_instance_uid": payload.study_instance_uid,
        }

    # 3. Обновляем статус заказа на ACQUIRED
    if order.status in [OrderStatus.IN_PROGRESS, OrderStatus.ARRIVED, OrderStatus.SCHEDULED]:
        order.status = OrderStatus.ACQUIRED

    await ws_manager.broadcast("worklist", {
        "type": "study_acquired",
        "order_id": str(order.id),
        "accession_number": order.accession_number,
        "status": order.status,
        "study_instance_uid": payload.study_instance_uid,
    })

    # 4. Создаём или обновляем Study
    study_result = await db.execute(
        select(Study).where(Study.order_id == order.id)
    )
    study = study_result.scalar_one_or_none()

    if study:
        study.study_instance_uid = payload.study_instance_uid
        study.orthanc_study_id = payload.orthanc_instance_id
        study.acquired_at = utc_now()
    else:
        study = Study(
            order_id=order.id,
            study_instance_uid=payload.study_instance_uid,
            orthanc_study_id=payload.orthanc_instance_id,
            acquired_at=utc_now(),
        )
        db.add(study)

    await db.flush()

    return {
        "status": "matched",
        "order_id": str(order.id),
        "order_status": order.status,
        "study_instance_uid": payload.study_instance_uid,
    }
