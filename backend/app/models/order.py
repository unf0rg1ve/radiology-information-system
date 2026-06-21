import uuid
from enum import Enum
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class OrderStatus(str, Enum):
    NEW = "NEW"
    SCHEDULED = "SCHEDULED"
    ARRIVED = "ARRIVED"
    IN_PROGRESS = "IN_PROGRESS"
    ACQUIRED = "ACQUIRED"
    TO_REPORT = "TO_REPORT"
    REPORTING = "REPORTING"
    SIGNED = "SIGNED"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    accession_number = Column(String(16), unique=True, nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=False)
    modality = Column(String(10), nullable=False)
    body_part = Column(String(100))
    priority = Column(String(10), nullable=False, default="ROUTINE")  # ROUTINE|URGENT
    financing_type = Column(String(10), nullable=False, default="PAID")  # GOMBP|OSMS|PAID
    referring_physician_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    referring_physician_name = Column(String(200))
    diagnosis_icd_id = Column(UUID(as_uuid=True), ForeignKey("diagnosis_icd.id"), nullable=True)
    clinical_notes = Column(Text)
    contrast_agent = Column(Boolean, default=False)
    status = Column(
        SAEnum(OrderStatus, name="order_status", native_enum=True),
        nullable=False,
        default=OrderStatus.NEW,
    )
    cancelled_reason = Column(Text)
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="orders", lazy="selectin")
    service = relationship("Service", lazy="selectin")
    referring_physician = relationship("User", foreign_keys=[referring_physician_id], lazy="selectin")
    diagnosis_icd = relationship("DiagnosisICD", lazy="selectin")
    appointment = relationship("Appointment", back_populates="order", uselist=False, lazy="selectin")
    study = relationship("Study", back_populates="order", uselist=False, lazy="selectin")
    reports = relationship("Report", back_populates="order", lazy="selectin")
