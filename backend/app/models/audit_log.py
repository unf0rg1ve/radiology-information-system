import uuid
from sqlalchemy import Column, String, DateTime, JSON, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.utils import utc_now


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    action = Column(String(20), nullable=False)  # CREATE|UPDATE|VIEW|SIGN|ISSUE|CANCEL
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    before_json = Column(JSON)
    after_json = Column(JSON)
    ip_address = Column(String(45))
    session_id = Column(String(100))
