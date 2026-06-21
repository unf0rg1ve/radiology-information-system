"""
Tests for the Orthanc webhook endpoint (Задача 3.2).
"""
import pytest
from sqlalchemy import select


class TestWebhookPayload:
    """Test the webhook payload schema."""

    def test_valid_payload(self):
        from app.api.webhook import OrthancStoredPayload
        payload = OrthancStoredPayload(
            study_instance_uid="1.2.826.0.1.3680043.9.7433.abc123",
            accession_number="260615-00001",
            orthanc_study_id="study-123",
            patient_id="900615350123",
            patient_name="Тестов^Тест",
            modality="CT",
            study_date="20260615",
        )
        assert payload.study_instance_uid == "1.2.826.0.1.3680043.9.7433.abc123"
        assert payload.accession_number == "260615-00001"
        assert payload.modality == "CT"

    def test_minimal_payload(self):
        """Webhook payload with only required fields."""
        from app.api.webhook import OrthancStoredPayload
        payload = OrthancStoredPayload(
            study_instance_uid="1.2.3.4.5",
        )
        assert payload.study_instance_uid == "1.2.3.4.5"
        assert payload.accession_number is None

    def test_empty_payload(self):
        """All fields are optional in the payload."""
        from app.api.webhook import OrthancStoredPayload
        payload = OrthancStoredPayload()
        assert payload.study_instance_uid is None
        assert payload.accession_number is None


class TestUnmatchedStudy:
    """Test the UnmatchedStudy model."""

    def test_model_fields(self):
        from app.models.unmatched_study import UnmatchedStudy
        # Check model has expected columns
        assert hasattr(UnmatchedStudy, 'study_instance_uid')
        assert hasattr(UnmatchedStudy, 'accession_number')
        assert hasattr(UnmatchedStudy, 'orthanc_study_id')
        assert hasattr(UnmatchedStudy, 'patient_id_dicom')
        assert hasattr(UnmatchedStudy, 'patient_name_dicom')
        assert hasattr(UnmatchedStudy, 'modality')
        assert hasattr(UnmatchedStudy, 'study_date')
        assert hasattr(UnmatchedStudy, 'raw_payload')
        assert hasattr(UnmatchedStudy, 'resolved')
        assert hasattr(UnmatchedStudy, 'resolved_order_id')
        assert hasattr(UnmatchedStudy, 'created_at')

    @pytest.mark.asyncio
    async def test_webhook_creates_unmatched_study(self, monkeypatch, client, test_db):
        """Unmatched webhook payload creates UnmatchedStudy record in DB."""
        from app.api import webhook
        monkeypatch.setattr(webhook.settings, 'WEBHOOK_SECRET', 'test-secret')

        payload = {
            "study_instance_uid": "1.2.826.0.1.3680043.9.7433.unmatched",
            "accession_number": "NO-SUCH-999",
            "orthanc_instance_id": "orthanc-study-unmatched",
            "patient_id": "PAT999",
            "patient_name": "UNMATCHED^PATIENT",
            "modality": "MR",
        }

        response = await client.post(
            "/api/webhook/orthanc/stored",
            json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unmatched"

        result = await test_db.execute(
            select(webhook.UnmatchedStudy).where(
                webhook.UnmatchedStudy.study_instance_uid == "1.2.826.0.1.3680043.9.7433.unmatched"
            )
        )
        unmatched = result.scalar_one_or_none()
        assert unmatched is not None
        assert unmatched.accession_number == "NO-SUCH-999"
        assert unmatched.orthanc_study_id == "orthanc-study-unmatched"
        assert unmatched.patient_id_dicom == "PAT999"
        assert unmatched.patient_name_dicom == "UNMATCHED^PATIENT"
        assert unmatched.modality == "MR"
        assert unmatched.resolved == "N"

    @pytest.mark.asyncio
    async def test_webhook_upserts_unmatched_study(self, monkeypatch, client, test_db):
        """Repeated webhook with same study_instance_uid updates raw_payload, not duplicate."""
        from app.api import webhook
        monkeypatch.setattr(webhook.settings, 'WEBHOOK_SECRET', 'test-secret')
        from app.models.unmatched_study import UnmatchedStudy

        uid = "1.2.826.0.1.3680043.9.7433.dup-test"
        unmatched = UnmatchedStudy(
            study_instance_uid=uid,
            accession_number="FIRST-AN",
            orthanc_study_id="first-orthanc",
            patient_id_dicom="PAT001",
            patient_name_dicom="FIRST^PATIENT",
            modality="CT",
            raw_payload={"first": True},
            resolved="N",
        )
        test_db.add(unmatched)
        await test_db.flush()

        payload = {
            "study_instance_uid": uid,
            "accession_number": "SECOND-AN",
            "orthanc_instance_id": "second-orthanc",
            "patient_id": "PAT002",
            "patient_name": "SECOND^PATIENT",
            "modality": "MR",
        }

        response = await client.post(
            "/api/webhook/orthanc/stored",
            json=payload,
            headers={"X-Webhook-Secret": "test-secret"},
        )
        assert response.status_code == 200

        result = await test_db.execute(
            select(UnmatchedStudy).where(UnmatchedStudy.study_instance_uid == uid)
        )
        records = result.scalars().all()
        assert len(records) == 1  # no duplicate
        updated = records[0]
        assert updated.accession_number == "FIRST-AN"  # untouched on upsert
        assert updated.raw_payload["accession_number"] == "SECOND-AN"  # raw_payload updated
