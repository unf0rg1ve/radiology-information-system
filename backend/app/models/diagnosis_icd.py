import uuid
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class DiagnosisICD(Base):
    __tablename__ = "diagnosis_icd"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(10), unique=True, nullable=False)
    name_ru = Column(String(300), nullable=False)
    name_kz = Column(String(300))
    chapter = Column(String(5))
    chapter_name_ru = Column(String(200))
    is_leaf = Column(Boolean, default=True)
