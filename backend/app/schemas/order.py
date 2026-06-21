from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.order import OrderStatus


class OrderCreate(BaseModel):
    patient_id: UUID
    service_id: UUID
    modality: str = Field(..., max_length=10)
    body_part: str | None = Field(None, max_length=100)
    priority: str = Field(default="ROUTINE", pattern="^(ROUTINE|URGENT)$")
    financing_type: str = Field(default="PAID", pattern="^(GOMBP|OSMS|PAID)$")
    referring_physician_id: UUID | None = None
    referring_physician_name: str | None = None
    diagnosis_icd_id: UUID | None = None
    clinical_notes: str | None = None
    contrast_agent: bool = False


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    reason: str | None = None


class OrderUpdate(BaseModel):
    body_part: str | None = Field(None, max_length=100)
    priority: str | None = Field(None, pattern="^(ROUTINE|URGENT)$")
    financing_type: str | None = Field(None, pattern="^(GOMBP|OSMS|PAID)$")
    diagnosis_icd_id: UUID | None = None
    clinical_notes: str | None = None
    contrast_agent: bool | None = None
    referring_physician_id: UUID | None = None
    referring_physician_name: str | None = None


class OrderResponse(BaseModel):
    id: UUID
    accession_number: str
    patient_id: UUID
    patient_name: str | None = None
    patient_iin: str | None = None
    service_id: UUID
    service_name: str | None = None
    modality: str
    body_part: str | None = None
    priority: str
    financing_type: str
    referring_physician_id: UUID | None = None
    referring_physician_name: str | None = None
    diagnosis_icd_id: UUID | None = None
    diagnosis_icd_code: str | None = None
    diagnosis_icd_name: str | None = None
    clinical_notes: str | None = None
    contrast_agent: bool
    status: OrderStatus
    cancelled_reason: str | None = None
    arrived_at: datetime | None = None
    created_at: datetime
    created_by: UUID | None = None

    class Config:
        from_attributes = True
