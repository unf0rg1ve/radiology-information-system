"""
Модель для несопоставленных исследований (orthanc studies без заказа в RIS).
"""
import uuid
from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.utils import utc_now


class UnmatchedStudy(Base):
    __tablename__ = "unmatched_studies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_instance_uid = Column(String(64), unique=True, nullable=False)
    accession_number = Column(String(16))
    orthanc_study_id = Column(String(64))
    patient_id_dicom = Column(String(100))  # PatientID из DICOM
    patient_name_dicom = Column(String(200))
    modality = Column(String(10))
    study_date = Column(String(8))
    raw_payload = Column(JSON)  # Полный payload от Orthanc webhook
    resolved = Column(String(1), default="N")  # N=не решено, Y=решено (связано вручную)
    resolved_order_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
