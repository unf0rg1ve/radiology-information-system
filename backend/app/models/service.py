import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Numeric, Integer, Boolean, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_gombp = Column(String(20), nullable=False)
    code_osms = Column(String(20))
    name_ru = Column(String(300), nullable=False)
    name_kz = Column(String(300))
    modality = Column(String(10), nullable=False)
    body_part = Column(String(100))
    tariff_gombp = Column(Numeric(10, 2))
    tariff_osms = Column(Numeric(10, 2))
    tariff_paid = Column(Numeric(10, 2))
    duration_min = Column(Integer, nullable=False, default=20)
    contrast_agent = Column(Boolean, default=False)
    valid_from = Column(Date, nullable=False, default=date(2020, 7, 1))
    valid_to = Column(Date)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
