from uuid import UUID
from pydantic import BaseModel


class OrganizationResponse(BaseModel):
    id: UUID
    name_ru: str
    name_kz: str | None
    license_number: str | None
    address: str | None
    phone: str | None

    class Config:
        from_attributes = True


class OrganizationUpdate(BaseModel):
    name_ru: str | None = None
    name_kz: str | None = None
    license_number: str | None = None
    address: str | None = None
    phone: str | None = None
