from uuid import UUID
from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class ServiceCreate(BaseModel):
    code_gombp: str
    code_osms: str | None = None
    name_ru: str
    name_kz: str | None = None
    modality: str
    body_part: str | None = None
    tariff_gombp: Decimal | None = None
    tariff_osms: Decimal | None = None
    tariff_paid: Decimal | None = None
    duration_min: int = 20
    contrast_agent: bool = False
    valid_from: date = date(2020, 7, 1)
    valid_to: date | None = None
    version: int = 1
    is_active: bool = True


class ServiceResponse(BaseModel):
    id: UUID
    code_gombp: str
    code_osms: str | None = None
    name_ru: str
    name_kz: str | None = None
    modality: str
    body_part: str | None = None
    tariff_gombp: Decimal | None = None
    tariff_osms: Decimal | None = None
    tariff_paid: Decimal | None = None
    duration_min: int
    contrast_agent: bool
    is_active: bool

    class Config:
        from_attributes = True
