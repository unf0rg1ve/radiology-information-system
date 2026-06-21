from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    order_id: UUID
    device_id: UUID
    slot_start: datetime
    slot_end: datetime


class AppointmentUpdate(BaseModel):
    slot_start: datetime
    slot_end: datetime
