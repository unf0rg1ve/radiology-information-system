from uuid import UUID
from pydantic import BaseModel


class ProtocolTemplateCreate(BaseModel):
    name_ru: str
    name_kz: str | None = None
    modality: str
    body_part: str | None = None
    service_id: UUID | None = None
    fields_schema: list[dict] = []
    description_template: str | None = None
    conclusion_template: str | None = None
    version: str = "1"
    is_active: bool = True


class ProtocolTemplateUpdate(BaseModel):
    name_ru: str | None = None
    name_kz: str | None = None
    modality: str | None = None
    body_part: str | None = None
    service_id: UUID | None = None
    fields_schema: list[dict] | None = None
    description_template: str | None = None
    conclusion_template: str | None = None
    version: str | None = None
    is_active: bool | None = None


class ProtocolTemplateResponse(BaseModel):
    id: UUID
    name_ru: str
    name_kz: str | None = None
    modality: str
    body_part: str | None = None
    service_id: UUID | None = None
    fields_schema: list[dict] | None = None
    description_template: str | None = None
    conclusion_template: str | None = None
    version: str
    is_active: bool

    class Config:
        from_attributes = True
