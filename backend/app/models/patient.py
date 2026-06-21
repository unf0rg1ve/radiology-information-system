import uuid
from datetime import date
from sqlalchemy import Column, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    iin = Column(String(12), unique=True, nullable=False)
    last_name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100))
    birth_date = Column(Date, nullable=False)
    gender = Column(String(1), nullable=False)  # M|F
    phone = Column(String(20))
    email = Column(String(200))
    benefit_category = Column(String(20), default="NONE")  # GOMBP|OSMS|DISABLED|NONE
    document_type = Column(String(20))
    document_number = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    orders = relationship("Order", back_populates="patient", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by])
