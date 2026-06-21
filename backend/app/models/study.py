import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class Study(Base):
    __tablename__ = "studies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False)
    study_instance_uid = Column(String(64), unique=True)
    orthanc_study_id = Column(String(64))
    technologist_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acquired_at = Column(DateTime(timezone=True))
    qc_status = Column(String(10))  # ACCEPTED|RETAKE
    qc_attempts = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    order = relationship("Order", back_populates="study", lazy="selectin")
    technologist = relationship("User", lazy="selectin")
