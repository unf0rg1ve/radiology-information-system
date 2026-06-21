from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import registrar_only, any_authenticated
from app.schemas.auth import UserMe
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, PatientSearchResult
from app.models.patient import Patient
from app.models.order import Order
from app.models.audit_log import AuditLog
from app.services.audit import json_safe
from app.core.utils import utc_now

router = APIRouter(prefix="/patients", tags=["Patients"])


def validate_iin(iin: str) -> bool:
    """Валидация ИИН: 12 цифр + контрольная цифра по алгоритму W1/W2 (ТЗ F1.2)."""
    if len(iin) != 12 or not iin.isdigit():
        return False

    weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]

    sum1 = sum(int(iin[i]) * weights1[i] for i in range(11))
    remainder = sum1 % 11

    if remainder == 10:
        sum2 = sum(int(iin[i]) * weights2[i] for i in range(11))
        remainder = sum2 % 11

    return remainder == int(iin[11])


@router.get("", response_model=list[PatientSearchResult])
async def list_patients(
    search: str = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(Patient)

    if search:
        search_lower = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Patient.iin).like(search_lower),
                func.lower(Patient.last_name).like(search_lower),
                func.lower(Patient.first_name).like(search_lower),
                func.lower(func.coalesce(Patient.middle_name, "")).like(search_lower),
                func.lower(Patient.last_name + " " + Patient.first_name).like(search_lower),
                func.lower(Patient.last_name + " " + Patient.first_name + " " + func.coalesce(Patient.middle_name, "")).like(search_lower),
                func.lower(func.coalesce(Patient.phone, "")).like(search_lower),
            )
        )

    count_query = select(func.count(Patient.id))
    if search:
        count_query = count_query.where(
            or_(
                func.lower(Patient.iin).like(search_lower),
                func.lower(Patient.last_name).like(search_lower),
                func.lower(Patient.first_name).like(search_lower),
                func.lower(func.coalesce(Patient.middle_name, "")).like(search_lower),
                func.lower(Patient.last_name + " " + Patient.first_name).like(search_lower),
                func.lower(Patient.last_name + " " + Patient.first_name + " " + func.coalesce(Patient.middle_name, "")).like(search_lower),
                func.lower(func.coalesce(Patient.phone, "")).like(search_lower),
            )
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Patient.last_name.asc(), Patient.first_name.asc())
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    patients = result.scalars().all()

    order_map = {}
    if patients:
        patient_ids = [p.id for p in patients]
        latest_subq = (
            select(
                Order.patient_id,
                func.max(Order.created_at).label("max_created_at"),
            )
            .where(Order.patient_id.in_(patient_ids))
            .group_by(Order.patient_id)
            .subquery()
        )
        latest_query = (
            select(Order)
            .join(
                latest_subq,
                and_(
                    Order.patient_id == latest_subq.c.patient_id,
                    Order.created_at == latest_subq.c.max_created_at,
                ),
            )
        )
        latest_result = await db.execute(latest_query)
        for o in latest_result.scalars().all():
            order_map[o.patient_id] = o

    return [
        PatientSearchResult(
            id=p.id,
            iin=p.iin,
            full_name=f"{p.last_name} {p.first_name} {p.middle_name or ''}".strip(),
            birth_date=p.birth_date,
            phone=p.phone,
            benefit_category=p.benefit_category,
            last_order_status=order_map[p.id].status.value if p.id in order_map else None,
            last_order_arrived_at=order_map[p.id].arrived_at if p.id in order_map else None,
        )
        for p in patients
    ]


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return patient


@router.get("/{patient_id}/history")
async def get_patient_history(
    patient_id: UUID,
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    """История исследований пациента с фильтром по периоду (ТЗ F1.4)."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    query = (
        select(Order)
        .where(Order.patient_id == patient_id)
        .order_by(Order.created_at.desc())
    )

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.where(Order.created_at >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.where(Order.created_at <= dt_to)
        except ValueError:
            pass

    orders_result = await db.execute(query)
    orders = orders_result.scalars().all()

    return {
        "patient_id": str(patient_id),
        "patient_name": f"{patient.last_name} {patient.first_name}",
        "total": len(orders),
        "orders": [
            {
                "id": str(o.id),
                "accession_number": o.accession_number,
                "modality": o.modality,
                "body_part": o.body_part,
                "service_name": o.service.name_ru if o.service else None,
                "status": o.status,
                "priority": o.priority,
                "financing_type": o.financing_type,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    }


@router.post("", response_model=PatientResponse)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(registrar_only),
):
    # Валидация ИИН (ТЗ F1.2)
    if not validate_iin(data.iin):
        raise HTTPException(status_code=422, detail="ИИН не прошёл контроль цифры")

    # Контроль дублей по ИИН (ТЗ F1.3)
    existing = await db.execute(select(Patient).where(Patient.iin == data.iin))
    existing_patient = existing.scalar_one_or_none()
    if existing_patient:
        raise HTTPException(
            status_code=409,
            detail=f"Пациент с таким ИИН уже существует",
        )

    patient = Patient(
        iin=data.iin,
        last_name=data.last_name,
        first_name=data.first_name,
        middle_name=data.middle_name,
        birth_date=data.birth_date,
        gender=data.gender,
        phone=data.phone,
        email=data.email,
        benefit_category=data.benefit_category,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(patient)
    await db.flush()
    await db.refresh(patient)

    audit = AuditLog(
        entity_type="Patient",
        entity_id=patient.id,
        action="CREATE",
        user_id=current_user.id,
        after_json=json_safe({
            "iin": patient.iin,
            "last_name": patient.last_name,
            "first_name": patient.first_name,
            "middle_name": patient.middle_name,
            "birth_date": str(patient.birth_date) if patient.birth_date else None,
            "gender": patient.gender,
            "phone": patient.phone,
            "email": patient.email,
            "benefit_category": patient.benefit_category,
            "patient_name": f"{patient.last_name} {patient.first_name[0]}.{' ' + patient.middle_name[0] + '.' if patient.middle_name else ''}",
        }),
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(registrar_only),
):
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    update_data = data.model_dump(exclude_unset=True)
    before = {field: json_safe(getattr(patient, field)) for field in update_data}
    for field, value in update_data.items():
        setattr(patient, field, value)
    after = {field: json_safe(getattr(patient, field)) for field in update_data}

    await db.flush()
    await db.refresh(patient)

    audit = AuditLog(
        entity_type="Patient",
        entity_id=patient.id,
        action="UPDATE",
        user_id=current_user.id,
        before_json=before,
        after_json=after,
        timestamp=utc_now(),
    )
    db.add(audit)
    await db.flush()

    return patient
