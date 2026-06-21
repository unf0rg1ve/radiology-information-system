import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    login = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(30), nullable=False)  # REGISTRAR|TECHNOLOGIST|RADIOLOGIST|HEAD|REFERRER|ADMIN
    last_name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100))
    specialization = Column(String(200))
    license_number = Column(String(50))
    email = Column(String(200))
    phone = Column(String(20))
    default_device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    notifications_cleared_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    default_device = relationship("Device", foreign_keys=[default_device_id])
