import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.utils import utc_now


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_ru = Column(String(200), nullable=False)
    name_kz = Column(String(200))
    license_number = Column(String(50))
    address = Column(Text)
    phone = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=utc_now)
