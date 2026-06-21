import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.utils import utc_now


class ProtocolTemplate(Base):
    __tablename__ = "protocol_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    name_ru = Column(String(200), nullable=False)
    name_kz = Column(String(200))
    modality = Column(String(10), nullable=False)
    body_part = Column(String(100))
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=True)
    fields_schema = Column(JSON, default=list)
    description_template = Column(Text)
    conclusion_template = Column(Text)
    version = Column(String(10), nullable=False, default="1")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
