from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ReportCreate(BaseModel):
    order_id: UUID
    protocol_template_id: UUID | None = None
    structured_fields: dict | None = None
    description_text: str | None = None
    conclusion_text: str | None = None
    critical_finding: bool = False
    diagnosis_icd_codes: list[str] | None = None


class ReportSignRequest(BaseModel):
    content_hash: str | None = None


class ReportResponse(BaseModel):
    id: UUID
    order_id: UUID
    accession_number: str | None = None
    patient_name: str | None = None
    service_name: str | None = None
    radiologist_id: UUID | None = None
    radiologist_name: str | None = None
    protocol_template_id: UUID | None = None
    structured_fields: dict | None = None
    description_text: str | None = None
    conclusion_text: str | None = None
    critical_finding: bool
    diagnosis_icd_codes: list[str] | None = None
    status: str
    version: str
    parent_report_id: UUID | None = None
    second_opinion_of_report_id: UUID | None = None
    signed_at: datetime | None = None
    content_hash: str | None = None
    issued_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
