from uuid import UUID
from datetime import time
from pydantic import BaseModel


class DeviceCreate(BaseModel):
    name: str
    modality_type: str
    ae_title: str
    ip_address: str | None = None
    dicom_port: int = 104
    schedule_start: time = time(8, 0)
    schedule_end: time = time(18, 0)
    working_days: list[int] = [1, 2, 3, 4, 5]
    status: str = "ACTIVE"
    notes: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    modality_type: str | None = None
    ae_title: str | None = None
    ip_address: str | None = None
    dicom_port: int | None = None
    schedule_start: time | None = None
    schedule_end: time | None = None
    working_days: list[int] | None = None
    status: str | None = None
    notes: str | None = None


class DeviceResponse(BaseModel):
    id: UUID
    name: str
    modality_type: str
    ae_title: str
    ip_address: str | None = None
    dicom_port: int
    schedule_start: time
    schedule_end: time
    working_days: list[int]
    status: str
    notes: str | None = None

    class Config:
        from_attributes = True
