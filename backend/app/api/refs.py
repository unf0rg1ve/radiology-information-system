from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import any_authenticated, admin_only
from app.schemas.auth import UserMe
from app.schemas.service import ServiceResponse, ServiceCreate
from app.schemas.device import DeviceResponse, DeviceCreate, DeviceUpdate
from app.schemas.diagnosis_icd import DiagnosisICDResponse
from app.schemas.protocol_template import ProtocolTemplateResponse, ProtocolTemplateCreate, ProtocolTemplateUpdate
from app.models.service import Service
from app.models.device import Device
from app.models.diagnosis_icd import DiagnosisICD
from app.models.protocol_template import ProtocolTemplate
from app.schemas.organization import OrganizationUpdate
from app.models.organization import Organization

router = APIRouter(prefix="/refs", tags=["References"])


# === Services (Tariff) ===
@router.get("/services", response_model=list[ServiceResponse])
async def list_services(
    modality: str = Query(None),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(Service).where(Service.is_active == True)
    if modality:
        query = query.where(Service.modality == modality)
    if search:
        query = query.where(
            func.lower(Service.name_ru).contains(search.lower()) |
            func.lower(Service.code_gombp).contains(search.lower())
        )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/services/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    return service


@router.post("/services", response_model=ServiceResponse)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    service = Service(**data.model_dump())
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


# === Devices ===
@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    modality: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(Device)
    if modality:
        query = query.where(Device.modality_type == modality)
    if status:
        query = query.where(Device.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Аппарат не найден")
    return device


@router.post("/devices", response_model=DeviceResponse)
async def create_device(
    data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    existing = await db.execute(select(Device).where(Device.ae_title == data.ae_title))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Аппарат с таким AE Title уже существует")

    device = Device(**data.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return device


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Аппарат не найден")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(device, field, value)

    await db.flush()
    await db.refresh(device)
    return device


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Аппарат не найден")

    device.status = "RETIRED"
    await db.flush()
    return {"status": "deleted"}


# === ICD-10 ===
@router.get("/icd10", response_model=list[DiagnosisICDResponse])
async def search_icd10(
    q: str = Query(None, min_length=1),
    chapter: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(DiagnosisICD)
    if q:
        search_lower = f"%{q.lower()}%"
        query = query.where(
            func.lower(DiagnosisICD.name_ru).like(search_lower) |
            func.lower(DiagnosisICD.code).like(search_lower)
        )
    if chapter:
        query = query.where(DiagnosisICD.chapter == chapter)
    query = query.where(DiagnosisICD.is_leaf == True).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/icd10/{icd_id}", response_model=DiagnosisICDResponse)
async def get_icd10(
    icd_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(DiagnosisICD).where(DiagnosisICD.id == icd_id))
    icd = result.scalar_one_or_none()
    if not icd:
        raise HTTPException(status_code=404, detail="Диагноз не найден")
    return icd


# === Protocol Templates ===
@router.get("/protocol-templates", response_model=list[ProtocolTemplateResponse])
async def list_templates(
    modality: str = Query(None),
    service_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    query = select(ProtocolTemplate).where(ProtocolTemplate.is_active == True)
    if modality:
        query = query.where(ProtocolTemplate.modality == modality)
    if service_id:
        query = query.where(ProtocolTemplate.service_id == service_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/protocol-templates/{template_id}", response_model=ProtocolTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(ProtocolTemplate).where(ProtocolTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return template


@router.post("/protocol-templates", response_model=ProtocolTemplateResponse)
async def create_template(
    data: ProtocolTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    template = ProtocolTemplate(**data.model_dump())
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.put("/protocol-templates/{template_id}", response_model=ProtocolTemplateResponse)
async def update_template(
    template_id: UUID,
    data: ProtocolTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    result = await db.execute(select(ProtocolTemplate).where(ProtocolTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)

    await db.flush()
    await db.refresh(template)
    return template


# === Organization ===
@router.get("/organization")
async def get_organization(
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        return {"name_ru": "", "license_number": "", "address": "", "phone": ""}
    return {
        "id": str(org.id),
        "name_ru": org.name_ru,
        "name_kz": org.name_kz,
        "license_number": org.license_number,
        "address": org.address,
        "phone": org.phone,
    }


@router.put("/organization")
async def update_organization(
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(admin_only),
):
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        org = Organization(**data.model_dump(exclude_unset=True))
        db.add(org)
    else:
        for field, value in data.model_dump(exclude_unset=True).items():
            if hasattr(org, field):
                setattr(org, field, value)
    await db.flush()
    await db.refresh(org)
    return {"status": "updated"}
