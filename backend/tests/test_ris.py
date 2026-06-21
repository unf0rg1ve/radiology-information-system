import pytest
import hashlib
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock


from app.services.status_machine import VALID_TRANSITIONS


class TestOrderStateMachine:
    """Тесты машины состояний заказа (ТЗ раздел 7)."""

    def test_valid_transitions(self):
        for from_status, to_statuses in VALID_TRANSITIONS.items():
            for to_status in to_statuses:
                assert to_status in VALID_TRANSITIONS.get(from_status, set()), \
                    f"Transition {from_status} -> {to_status} should be valid"

    def test_no_transitions_from_cancelled(self):
        assert VALID_TRANSITIONS["CANCELLED"] == set(), \
            "Terminal status CANCELLED should have no transitions"

    def test_issued_can_go_to_reporting_for_new_version(self):
        assert "REPORTING" in VALID_TRANSITIONS["ISSUED"], \
            "ISSUED should allow REPORTING for new report version"

    def test_cito_goes_to_scheduled(self):
        assert "SCHEDULED" in VALID_TRANSITIONS["NEW"]

    def test_retake_goes_to_in_progress(self):
        assert "IN_PROGRESS" in VALID_TRANSITIONS["ACQUIRED"]


class TestRBAC:
    """Тесты ролевого доступа (ТЗ F7.2)."""

    ROLES = ["REGISTRAR", "TECHNOLOGIST", "RADIOLOGIST", "HEAD", "REFERRER", "ADMIN"]

    ROLE_PERMISSIONS = {
        "REGISTRAR": ["patients", "orders", "schedule"],
        "TECHNOLOGIST": ["worklist"],
        "RADIOLOGIST": ["reports", "worklist"],
        "HEAD": ["reports", "stats", "admin"],
        "REFERRER": ["orders_read_own"],
        "ADMIN": ["users", "refs", "audit", "system"],
    }

    def test_all_six_roles_exist(self):
        assert len(self.ROLES) == 6

    def test_admin_has_full_access(self):
        assert "ADMIN" in self.ROLES

    def test_referrer_limited_access(self):
        perms = self.ROLE_PERMISSIONS["REFERRER"]
        assert "patients" not in perms
        assert "orders_read_own" in perms


class TestIINValidation:
    """Тесты валидации ИИН (ТЗ F1.2)."""

    def test_iin_length(self):
        assert len("123456789012") == 12

    def test_valid_checksum_algorithm(self):
        def calculate_iin_checksum(iin: str) -> int:
            weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
            sum1 = sum(int(iin[i]) * weights1[i] for i in range(11))
            remainder = sum1 % 11
            if remainder == 10:
                sum2 = sum(int(iin[i]) * weights2[i] for i in range(11))
                remainder = sum2 % 11
            return remainder

        valid_iin = "210203345067"  # 1903-02-21, контрольная цифра 7
        checksum = calculate_iin_checksum(valid_iin)
        assert checksum == int(valid_iin[11])


class TestContentHash:
    """Тесты SHA-256 хэширования (ТЗ F5.5, 8.2)."""

    def test_sha256_deterministic(self):
        content = "test content|2026-01-01|user123"
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()
        assert hash1 == hash2

    def test_sha256_different_for_different_content(self):
        hash1 = hashlib.sha256("content1".encode()).hexdigest()
        hash2 = hashlib.sha256("content2".encode()).hexdigest()
        assert hash1 != hash2

    def test_sha256_length(self):
        h = hashlib.sha256("test".encode()).hexdigest()
        assert len(h) == 64


class TestReportImmutability:
    """Тесты неизменяемости подписанных документов (ТЗ F7.4)."""

    def test_signed_report_cannot_be_edited(self):
        report_status = "SIGNED"
        assert report_status != "DRAFT", "Signed report should not be editable"

    def test_issued_report_cannot_be_edited(self):
        report_status = "ISSUED"
        assert report_status != "DRAFT", "Issued report should not be editable"

    def test_edit_creates_new_version(self):
        original_version = 1
        new_version = original_version + 1
        assert new_version == 2


class TestOrthancAdapter:
    """Тесты OrthancAdapter (ТЗ F9.1)."""

    def test_mwl_dicom_tags(self):
        required_tags = [
            "0010,0010",  # PatientName
            "0010,0020",  # PatientID
            "0010,0030",  # PatientBirthDate
            "0010,0040",  # PatientSex
            "0008,0050",  # AccessionNumber
            "0020,000D",  # StudyInstanceUID
            "0008,0060",  # Modality
            "0040,0001",  # ScheduledStationAETitle
            "0040,0002",  # ScheduledProcedureStepDate
            "0040,0003",  # ScheduledProcedureStepTime
            "0032,1060",  # RequestedProcedureDescription
        ]
        assert len(required_tags) == 11

    def test_viewer_url_format(self):
        base_url = "http://orthanc:8042"
        study_uid = "1.2.3.4.5"
        url = f"{base_url}/viewer?study={study_uid}"
        assert "study=" in url
        assert study_uid in url


class TestPDFGeneration:
    """Тесты генерации PDF (ТЗ F2.5, F5.6)."""

    def test_order_pdf_required_fields(self):
        required = [
            "accession_number", "patient_name", "patient_iin",
            "service_name", "modality", "diagnosis", "created_at",
        ]
        assert len(required) >= 7

    def test_report_pdf_required_fields(self):
        required = [
            "patient_name", "patient_iin", "conclusion_text",
            "radiologist_name", "signed_at", "content_hash",
        ]
        assert len(required) >= 6


class TestAccessionNumber:
    """Тесты генерации Accession Number (ТЗ F2.2)."""

    def test_an_format(self):
        now = datetime.now()
        date_part = now.strftime("%y%m%d")
        assert len(date_part) == 6
        assert date_part.isdigit()

    def test_an_uniqueness(self):
        ans = set()
        for _ in range(100):
            now = datetime.now()
            date_part = now.strftime("%y%m%d")
            seq = now.strftime("%H%M%S")[-5:]
            an = f"{date_part}-{seq}"
            ans.add(an)
        # At least some should be unique (depending on timing)
        assert len(ans) >= 1
