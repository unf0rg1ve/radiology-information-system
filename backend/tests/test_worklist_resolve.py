"""
Tests for unmatched study resolution endpoint (F4.5).
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock


class TestResolveUnmatchedStudy:

    def test_unmatched_study_model_fields(self):
        from app.models.unmatched_study import UnmatchedStudy
        assert hasattr(UnmatchedStudy, 'study_instance_uid')
        assert hasattr(UnmatchedStudy, 'resolved')
        assert hasattr(UnmatchedStudy, 'resolved_order_id')

    @pytest.mark.asyncio
    async def test_get_unmatched_returns_unresolved(self, monkeypatch, client, test_db):
        from app.api import worklist
        from app.models.unmatched_study import UnmatchedStudy
        from app.auth.jwt import create_access_token
        from app.models.user import User
        from app.models.organization import Organization

        async def skip_orthanc_sync(db):
            return None

        monkeypatch.setattr(worklist, "sync_orthanc_studies", skip_orthanc_sync)

        org = Organization(name_ru="Test Org", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()
        admin = User(org_id=org.id, login="resolve_admin", role="ADMIN",
                      password_hash="x", last_name="A", first_name="A", is_active=True)
        test_db.add(admin)
        await test_db.flush()

        token = create_access_token(str(admin.id), admin.login, admin.role, admin.first_name, admin.last_name)

        unmatched = UnmatchedStudy(
            study_instance_uid="1.2.3.4.5.test-unmatched",
            accession_number="AN-TEST-001",
            orthanc_study_id="orth-test-001",
            patient_id_dicom="PAT001",
            patient_name_dicom="TEST^PATIENT",
            modality="CT",
            resolved="N",
        )
        test_db.add(unmatched)
        resolved = UnmatchedStudy(
            study_instance_uid="1.2.3.4.5.test-resolved",
            accession_number="AN-TEST-002",
            orthanc_study_id="orth-test-002",
            patient_id_dicom="PAT002",
            patient_name_dicom="TEST^RESOLVED",
            modality="MR",
            resolved="Y",
        )
        test_db.add(resolved)
        await test_db.flush()

        response = await client.get(
            "/api/worklist/unmatched",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["study_instance_uid"] == "1.2.3.4.5.test-unmatched"
        assert data[0]["accession_number"] == "AN-TEST-001"

    @pytest.mark.asyncio
    async def test_radiologist_can_view_and_resolve_unmatched_study(self, monkeypatch, client, test_db):
        from app.api import worklist
        from app.models.unmatched_study import UnmatchedStudy
        from app.models.order import Order
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.user import User
        from app.models.organization import Organization
        from app.models.study import Study
        from app.auth.jwt import create_access_token
        from sqlalchemy import select

        async def skip_orthanc_sync(db):
            return None

        monkeypatch.setattr(worklist, "sync_orthanc_studies", skip_orthanc_sync)

        org = Organization(name_ru="Test Org Rad", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()

        from datetime import date
        patient = Patient(iin="123456789013", last_name="Петров", first_name="Петр",
                          gender="M", birth_date=date(1985, 5, 5))
        test_db.add(patient)
        await test_db.flush()

        service = Service(code_gombp="01.002", name_ru="КТ", modality="CT",
                          tariff_paid=1000.0, is_active=True)
        test_db.add(service)
        await test_db.flush()

        radiologist = User(org_id=org.id, login="resolve_radiologist", role="RADIOLOGIST",
                            password_hash="x", last_name="R", first_name="R", is_active=True)
        test_db.add(radiologist)
        await test_db.flush()

        order = Order(
            accession_number="RAD-RESOLVE-001",
            patient_id=patient.id,
            service_id=service.id,
            modality="CT",
            body_part="Головной мозг",
            priority="ROUTINE",
            financing_type="PAID",
            status="IN_PROGRESS",
            created_by=radiologist.id,
        )
        test_db.add(order)
        await test_db.flush()

        unmatched = UnmatchedStudy(
            study_instance_uid="1.2.3.4.5.radiologist-resolve",
            accession_number=None,
            orthanc_study_id="orth-rad-resolve",
            patient_id_dicom="PAT-RAD",
            patient_name_dicom=None,
            modality=None,
            raw_payload={"patient_name_dicom": "RAD TEST", "modality": "CT"},
            resolved="N",
        )
        test_db.add(unmatched)
        await test_db.flush()

        token = create_access_token(
            str(radiologist.id),
            radiologist.login,
            radiologist.role,
            radiologist.first_name,
            radiologist.last_name,
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/worklist/unmatched", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data[0]["patient_name_dicom"] == "RAD TEST"
        assert data[0]["modality"] == "CT"

        response = await client.post(
            f"/api/worklist/unmatched/{unmatched.id}/resolve",
            json={"order_id": str(order.id)},
            headers=headers,
        )
        assert response.status_code == 200

        await test_db.refresh(unmatched)
        study = (await test_db.execute(
            select(Study).where(Study.order_id == order.id)
        )).scalar_one()
        assert unmatched.resolved == "Y"
        assert study.study_instance_uid == "1.2.3.4.5.radiologist-resolve"

    @pytest.mark.asyncio
    async def test_resolve_unmatched_study(self, monkeypatch, client, test_db):
        from app.models.unmatched_study import UnmatchedStudy
        from app.models.order import Order
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.user import User
        from app.models.organization import Organization
        from app.auth.jwt import create_access_token

        org = Organization(name_ru="Test Org", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()

        from datetime import date
        patient = Patient(iin="123456789012", last_name="Иванов", first_name="Иван",
                          gender="M", birth_date=date(1990, 1, 1))
        test_db.add(patient)
        await test_db.flush()

        service = Service(code_gombp="01.001", name_ru="КТ головного мозга", modality="CT",
                          tariff_paid=1000.0, is_active=True)
        test_db.add(service)
        await test_db.flush()

        admin = User(org_id=org.id, login="resolve_admin2", role="ADMIN",
                      password_hash="x", last_name="A", first_name="A", is_active=True)
        test_db.add(admin)
        await test_db.flush()

        order = Order(
            accession_number="RESOLVE-AN-001",
            patient_id=patient.id,
            service_id=service.id,
            modality="CT",
            body_part="Головной мозг",
            priority="ROUTINE",
            financing_type="PAID",
            status="IN_PROGRESS",
            created_by=admin.id,
        )
        test_db.add(order)
        await test_db.flush()

        unmatched = UnmatchedStudy(
            study_instance_uid="1.2.3.4.5.resolve-test",
            accession_number="RESOLVE-AN-001",
            orthanc_study_id="orth-resolve-001",
            patient_id_dicom="PAT_RESOLVE",
            patient_name_dicom="RESOLVE^TEST",
            modality="CT",
            resolved="N",
        )
        test_db.add(unmatched)
        await test_db.flush()

        token = create_access_token(str(admin.id), admin.login, admin.role, admin.first_name, admin.last_name)

        response = await client.post(
            f"/api/worklist/unmatched/{unmatched.id}/resolve",
            json={"order_id": str(order.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["order_id"] == str(order.id)

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_returns_409(self, monkeypatch, client, test_db):
        from app.models.unmatched_study import UnmatchedStudy
        from app.models.user import User
        from app.models.organization import Organization
        from app.auth.jwt import create_access_token

        org = Organization(name_ru="Test Org 3", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()

        admin = User(org_id=org.id, login="resolve_admin3", role="ADMIN",
                      password_hash="x", last_name="A", first_name="A", is_active=True)
        test_db.add(admin)
        await test_db.flush()

        unmatched = UnmatchedStudy(
            study_instance_uid="1.2.3.4.5.already-resolved",
            accession_number="AN-ALREADY",
            resolved="Y",
        )
        test_db.add(unmatched)
        await test_db.flush()

        token = create_access_token(str(admin.id), admin.login, admin.role, admin.first_name, admin.last_name)

        response = await client.post(
            f"/api/worklist/unmatched/{unmatched.id}/resolve",
            json={"order_id": str(uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_unmatched_returns_404(self, monkeypatch, client, test_db):
        from app.models.user import User
        from app.models.organization import Organization
        from app.auth.jwt import create_access_token

        org = Organization(name_ru="Test Org 4", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()

        admin = User(org_id=org.id, login="resolve_admin4", role="ADMIN",
                      password_hash="x", last_name="A", first_name="A", is_active=True)
        test_db.add(admin)
        await test_db.flush()

        token = create_access_token(str(admin.id), admin.login, admin.role, admin.first_name, admin.last_name)

        response = await client.post(
            f"/api/worklist/unmatched/{str(uuid4())}/resolve",
            json={"order_id": str(uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
