import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    radiologist_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    protocol_template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), nullable=True)
    structured_fields = Column(JSON, default=dict)
    description_text = Column(Text)
    conclusion_text = Column(Text)
    critical_finding = Column(Boolean, default=False)
    diagnosis_icd_codes = Column(ARRAY(String), default=list)
    status = Column(String(10), nullable=False, default="DRAFT")  # DRAFT|SIGNED|ISSUED
    version = Column(String(10), nullable=False, default="1")
    parent_report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=True)
    second_opinion_of_report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=True)
    signed_at = Column(DateTime(timezone=True))
    content_hash = Column(String(64))
    issued_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    order = relationship("Order", back_populates="reports", lazy="selectin")
    radiologist = relationship("User", lazy="selectin")
    protocol_template = relationship("ProtocolTemplate", lazy="selectin")
