"""Синхронизация исследований Orthanc ↔ RIS."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.orthanc import orthanc_adapter
from app.models.order import Order, OrderStatus
from app.models.study import Study
from app.models.unmatched_study import UnmatchedStudy
from app.core.utils import utc_now


async def link_study_to_order(
    db: AsyncSession,
    order: Order,
    study_instance_uid: str,
    orthanc_study_id: str | None,
) -> Study:
    """Создать или обновить запись Study для заказа."""
    result = await db.execute(select(Study).where(Study.order_id == order.id))
    study = result.scalar_one_or_none()
    if study:
        study.study_instance_uid = study_instance_uid
        study.orthanc_study_id = orthanc_study_id
        study.acquired_at = study.acquired_at or utc_now()
    else:
        study = Study(
            order_id=order.id,
            study_instance_uid=study_instance_uid,
            orthanc_study_id=orthanc_study_id,
            acquired_at=utc_now(),
        )
        db.add(study)

    if order.status in (
        OrderStatus.SCHEDULED,
        OrderStatus.ARRIVED,
        OrderStatus.IN_PROGRESS,
    ):
        order.status = OrderStatus.ACQUIRED

    await db.flush()
    return study


async def sync_orthanc_studies(db: AsyncSession) -> None:
    """Импортировать из Orthanc студии без связи с RIS (в unmatched или автосопоставление по AN)."""
    if not await orthanc_adapter.verify_connection():
        return

    summaries = await orthanc_adapter.list_study_summaries()
    for summary in summaries:
        study_uid = summary.get("study_instance_uid")
        if not study_uid:
            continue

        linked = await db.execute(
            select(Study).where(Study.study_instance_uid == study_uid)
        )
        if linked.scalar_one_or_none():
            continue

        accession = summary.get("accession_number") or None
        if accession:
            order_result = await db.execute(
                select(Order).where(Order.accession_number == accession)
            )
            order = order_result.scalar_one_or_none()
            if order:
                await link_study_to_order(
                    db,
                    order,
                    study_uid,
                    summary.get("orthanc_study_id"),
                )
                continue

        existing_unmatched_result = await db.execute(
            select(UnmatchedStudy).where(
                UnmatchedStudy.study_instance_uid == study_uid
            )
        )
        existing_unmatched = existing_unmatched_result.scalar_one_or_none()
        if existing_unmatched:
            if existing_unmatched.resolved == "N":
                existing_unmatched.accession_number = accession
                existing_unmatched.orthanc_study_id = summary.get("orthanc_study_id")
                existing_unmatched.patient_id_dicom = summary.get("patient_id_dicom")
                existing_unmatched.patient_name_dicom = summary.get("patient_name_dicom")
                existing_unmatched.modality = summary.get("modality")
                existing_unmatched.study_date = summary.get("study_date")
                existing_unmatched.raw_payload = summary
            continue

        db.add(
            UnmatchedStudy(
                study_instance_uid=study_uid,
                accession_number=accession,
                orthanc_study_id=summary.get("orthanc_study_id"),
                patient_id_dicom=summary.get("patient_id_dicom"),
                patient_name_dicom=summary.get("patient_name_dicom"),
                modality=summary.get("modality"),
                study_date=summary.get("study_date"),
                raw_payload=summary,
                resolved="N",
            )
        )

    await db.flush()


async def resolve_study_for_order(db: AsyncSession, order: Order) -> Study | None:
    """Найти Study в БД или сопоставить с Orthanc."""
    result = await db.execute(select(Study).where(Study.order_id == order.id))
    study = result.scalar_one_or_none()

    # If study has a real orthanc_study_id, it's fully resolved
    if study and study.study_instance_uid and study.orthanc_study_id:
        return study

    # If study has a placeholder UID (2.25.xxx) or no UID, try to find real study in Orthanc
    await sync_orthanc_studies(db)

    result = await db.execute(select(Study).where(Study.order_id == order.id))
    study = result.scalar_one_or_none()

    # Re-check after sync
    if study and study.study_instance_uid and study.orthanc_study_id:
        return study

    if not await orthanc_adapter.verify_connection():
        return study

    # If we have a placeholder UID, try to find the real study by accession number
    summary = await orthanc_adapter.find_study_summary_by_accession(order.accession_number)
    if summary:
        return await link_study_to_order(
            db,
            order,
            summary["study_instance_uid"],
            summary.get("orthanc_study_id"),
        )

    # If we have a UID but no orthanc_study_id, check if it actually exists in Orthanc
    if study and study.study_instance_uid and not study.orthanc_study_id:
        if await orthanc_adapter.study_exists(study.study_instance_uid):
            orthanc_id = await orthanc_adapter.resolve_orthanc_study_id(study.study_instance_uid)
            study.orthanc_study_id = orthanc_id
            study.acquired_at = study.acquired_at or utc_now()
            await db.flush()
        else:
            # Placeholder UID not found in Orthanc — images not yet received
            pass

    return study
