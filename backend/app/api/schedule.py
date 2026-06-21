from uuid import UUID
from datetime import datetime, date, time, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import registrar_only, any_authenticated
from app.schemas.auth import UserMe
from app.models.appointment import Appointment
from app.models.device import Device
from app.models.order import Order, OrderStatus
from app.models.service import Service
from app.adapters.orthanc import orthanc_adapter
from app.models.study import Study
from app.services.dicom_uid import generate_study_instance_uid
from app.schemas.schedule import AppointmentCreate, AppointmentUpdate
from app.core.utils import utc_now

router = APIRouter(prefix="/schedule", tags=["Schedule"])


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/slots")
async def get_slots(
    device_id: UUID,
    date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    # Get device
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Аппарат не найден")
    
    start_dt = datetime.combine(date, time(0, 0), tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.device_id == device_id,
                Appointment.slot_start < end_dt,
                Appointment.slot_end > start_dt,
            )
        )
    )
    appointments = result.scalars().all()
    
    # Generate time slots
    slots = []
    current = datetime.combine(date, device.schedule_start or time(8, 0), tzinfo=timezone.utc)
    end = datetime.combine(date, device.schedule_end or time(18, 0), tzinfo=timezone.utc)
    slot_duration = timedelta(minutes=30)  # Default slot duration
    
    while current + slot_duration <= end:
        slot_end = current + slot_duration
        occupied = None
        for appt in appointments:
            if appt.slot_start < slot_end and appt.slot_end > current:
                occupied = appt
                break
        
        slots.append({
            "start": current.isoformat(),
            "end": slot_end.isoformat(),
            "occupied": occupied is not None,
            "appointment": {
                "id": str(occupied.id),
                "order_id": str(occupied.order_id),
                "accession_number": occupied.order.accession_number if occupied and occupied.order else None,
                "order_status": occupied.order.status.value if occupied and occupied.order and occupied.order.status else None,
                "slot_start": occupied.slot_start.isoformat(),
                "slot_end": occupied.slot_end.isoformat(),
                "patient_name": occupied.order.patient.last_name + " " + occupied.order.patient.first_name if occupied and occupied.order and occupied.order.patient else None,
            } if occupied else None,
        })
        current = slot_end
    
    return {
        "device_id": str(device_id),
        "device_name": device.name,
        "date": date.isoformat(),
        "slots": slots,
    }


@router.post("/appointments")
async def create_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(registrar_only),
):
    slot_start = _as_utc(data.slot_start)
    # Determine actual slot duration from order service
    order_result = await db.execute(select(Order).where(Order.id == data.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")
    if slot_start < utc_now():
        raise HTTPException(status_code=422, detail="Нельзя записать пациента на прошедшее время")

    device_result = await db.execute(select(Device).where(Device.id == data.device_id))
    device = device_result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Аппарат не найден")
    if device.modality_type.upper() != order.modality.upper():
        raise HTTPException(
            status_code=422,
            detail=(
                f"Несоответствие типа аппарата и модальности исследования. "
                f"Аппарат «{device.name}» — это {device.modality_type}, "
                f"а направление требует {order.modality}. "
                f"Выберите аппарат с модальностью {order.modality}."
            ),
        )
    if device.status != "ACTIVE":
        raise HTTPException(
            status_code=422,
            detail=f"Аппарат «{device.name}» недоступен (статус: {device.status}). Выберите другой аппарат.",
        )

    service_result = await db.execute(select(Service).where(Service.id == order.service_id))
    service = service_result.scalar_one_or_none()
    duration_min = service.duration_min if service and service.duration_min else 30
    actual_slot_end = slot_start + timedelta(minutes=duration_min)

    # Check for double booking using actual duration
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.device_id == data.device_id,
                Appointment.slot_start < actual_slot_end,
                Appointment.slot_end > slot_start,
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Слот уже занят")

    appointment = Appointment(
        order_id=data.order_id,
        device_id=data.device_id,
        technologist_id=current_user.id,
        slot_start=slot_start,
        slot_end=actual_slot_end,
    )
    db.add(appointment)
    
    # Update order status
    if order:
        order.status = OrderStatus.SCHEDULED

        # Публикация в DICOM MWL (ТЗ F4.1)
        # Создаём/обновляем Study с валидным DICOM StudyInstanceUID для последующего авто-сопоставления
        study_uid = generate_study_instance_uid()
        study_result = await db.execute(select(Study).where(Study.order_id == data.order_id))
        study = study_result.scalar_one_or_none()
        if study:
            study.study_instance_uid = study_uid
        else:
            study = Study(
                order_id=data.order_id,
                study_instance_uid=study_uid,
            )
            db.add(study)

        try:
            device_result = await db.execute(select(Device).where(Device.id == data.device_id))
            device = device_result.scalar_one_or_none()

            service_result = await db.execute(select(Service).where(Service.id == order.service_id))
            service = service_result.scalar_one_or_none()

            if device and order.patient:
                patient = order.patient
                # Форматы дат по DICOM: YYYYMMDD
                birth_date = patient.birth_date.strftime("%Y%m%d") if patient.birth_date else ""
                sched_date = slot_start.strftime("%Y%m%d")
                sched_time = slot_start.strftime("%H%M%S")

                await orthanc_adapter.publish_mwl(
                    accession_number=order.accession_number,
                    patient_name=f"{patient.last_name}^{patient.first_name}^{patient.middle_name or ''}",
                    patient_id=patient.iin,
                    patient_birth_date=birth_date,
                    patient_sex=patient.gender or "O",
                    study_instance_uid=study_uid,
                    modality=order.modality,
                    ae_title=device.ae_title,
                    scheduled_date=sched_date,
                    scheduled_time=sched_time,
                    procedure_description=service.name_ru if service else order.modality,
                )
        except Exception as e:
            # MWL публикация не критична — логируем ошибку
            import logging
            logging.warning(f"Failed to publish MWL for order {order.id}: {e}")

    await db.flush()
    await db.refresh(appointment)
    return {"id": str(appointment.id), "status": OrderStatus.SCHEDULED.value}


@router.delete("/appointments/{appointment_id}")
async def cancel_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(registrar_only),
):
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    # Update order status back to NEW
    order_result = await db.execute(select(Order).where(Order.id == appointment.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = OrderStatus.NEW

    await db.delete(appointment)
    await db.flush()
    return {"status": "cancelled"}


@router.put("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(registrar_only),
):
    """Перенос записи на новый слот (ТЗ F3.2)."""
    slot_start = _as_utc(data.slot_start)
    slot_end = _as_utc(data.slot_end)
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if slot_start < utc_now():
        raise HTTPException(status_code=422, detail="Нельзя перенести запись на прошедшее время")

    # Проверяем конфликт с другими записями (исключая текущую)
    conflict_result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.device_id == appointment.device_id,
                Appointment.id != appointment_id,
                Appointment.slot_start < slot_end,
                Appointment.slot_end > slot_start,
            )
        )
    )
    if conflict_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Новый слот уже занят")

    appointment.slot_start = slot_start
    appointment.slot_end = slot_end

    await db.flush()
    await db.refresh(appointment)
    return {"id": str(appointment.id), "status": "rescheduled"}
