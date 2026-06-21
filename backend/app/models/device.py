import uuid
from datetime import time
from sqlalchemy import Column, String, Integer, DateTime, Time, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.core.database import Base
from app.core.utils import utc_now


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    name = Column(String(200), nullable=False)
    modality_type = Column(String(10), nullable=False)
    ae_title = Column(String(16), unique=True, nullable=False)
    ip_address = Column(String(15))
    dicom_port = Column(Integer, default=104)
    schedule_start = Column(Time, default=time(8, 0))
    schedule_end = Column(Time, default=time(18, 0))
    working_days = Column(ARRAY(Integer), default=list)
    status = Column(String(20), default="ACTIVE")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)
