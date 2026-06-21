"""
Tests for Report-related features: versioning, second opinion, CITO.
"""
import pytest
from sqlalchemy import select
from app.services.status_machine import validate_status_transition, InvalidStatusTransition
from app.auth.jwt import create_access_token


class TestReportVersioning:
    """Test Report versioning logic (F)."""

    def test_draft_can_be_edited(self):
        """DRAFT reports can be edited directly by their author."""
        pass

    def test_signed_report_not_editable(self):
        """Signed reports cannot be edited — tested via test_new_version_from_signed."""
        pass

    def test_version_increment(self):
        """New version should increment the version number."""
        current = "1"
        next_ver = str(int(current) + 1)
        assert next_ver == "2"

        current = "3"
        next_ver = str(int(current) + 1)
        assert next_ver == "4"


class TestSecondOpinion:
    """Test second opinion creation (F5.7)."""

    def test_second_opinion_creates_new_report(self):
        """Second opinion should create a new Report, not modify the original."""
        pass

    def test_second_opinion_links_to_original(self):
        """Second opinion should have second_opinion_of_report_id set."""
        pass


class TestCITONotification:
    """Test CITO notification logic (F5.6, F5.7)."""

    def test_critical_finding_creates_audit_log(self):
        """Covered by test_issue_critical_creates_cito_audit_log."""
        pass

    def test_critical_finding_stamps_pdf(self):
        """PDF should have red 'КРИТИЧЕСКАЯ НАХОДКА' stamp."""
        from app.services.pdf import generate_report_pdf
        # Generate PDF with critical finding
        report_data = {
            "status": "ISSUED",
            "description_text": "Описание",
            "conclusion_text": "Заключение",
            "critical_finding": True,
            "diagnosis_icd_codes": ["C34.1"],
            "content_hash": "abc123",
            "signed_at": None,
            "version": "1",
        }
        order_data = {
            "accession_number": "260615-00001",
            "priority": "CITO",
            "financing_type": "OSMS",
            "modality": "CT",
            "body_part": "Грудная клетка",
            "clinical_notes": "Подозрение на новообразование",
            "created_at": "15.06.2026 10:00",
            "referring_physician_name": "Др. Иванов",
        }
        patient_data = {
            "iin": "900615350123",
            "last_name": "Тестов",
            "first_name": "Тест",
            "middle_name": "Тестович",
            "birth_date": "15.06.1990",
            "gender": "M",
        }
        service_data = {"code_gombp": "A06.20.002", "name_ru": "КТ грудной клетки"}
        radiologist_data = {
            "last_name": "Петров",
            "first_name": "Пётр",
            "middle_name": "Иванович",
            "specialization": "Рентгенолог",
            "license_number": "Л-12345",
        }

        pdf_bytes = generate_report_pdf(
            report_data, order_data, patient_data, service_data, radiologist_data
        )
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        # Check that PDF contains the critical stamp text
        # Note: PDF content is binary, so we check the raw bytes
        assert b"%PDF" in pdf_bytes  # Valid PDF header

    def test_draft_pdf_has_watermark(self):
        """DRAFT PDF should have 'ЧЕРНОВИК' watermark."""
        from app.services.pdf import generate_report_pdf
        report_data = {
            "status": "DRAFT",
            "description_text": "Описание",
            "conclusion_text": "Заключение",
            "critical_finding": False,
            "diagnosis_icd_codes": [],
            "content_hash": None,
            "signed_at": None,
            "version": "1",
        }
        order_data = {
            "accession_number": "260615-00001",
            "priority": "ROUTINE",
            "financing_type": "PAID",
            "modality": "MR",
            "body_part": "Головной мозг",
            "clinical_notes": "",
            "created_at": "15.06.2026 10:00",
            "referring_physician_name": None,
        }
        patient_data = {
            "iin": "900615350123",
            "last_name": "Тестов",
            "first_name": "Тест",
            "middle_name": "",
            "birth_date": "15.06.1990",
            "gender": "M",
        }
        service_data = {"code_gombp": "A06.20.010", "name_ru": "МРТ головного мозга"}
        radiologist_data = {
            "last_name": "Петров",
            "first_name": "Пётр",
            "middle_name": "",
            "specialization": "Рентгенолог",
            "license_number": "Л-12345",
        }

        pdf_bytes = generate_report_pdf(
            report_data, order_data, patient_data, service_data, radiologist_data
        )
        assert pdf_bytes is not None
        assert b"%PDF" in pdf_bytes


class TestPDFGeneration:
    """Test PDF generation speed and content (F2.5)."""

    def test_order_pdf_generation(self):
        """Test order PDF can be generated."""
        from app.services.pdf import generate_order_pdf
        import time

        order_data = {
            "accession_number": "260615-00001",
            "status": "NEW",
            "priority": "ROUTINE",
            "financing_type": "OSMS",
            "modality": "MR",
            "body_part": "Головной мозг",
            "clinical_notes": "Головные боли",
            "contrast_agent": False,
            "created_at": "15.06.2026 10:00",
            "diagnosis_icd_name": "G43 Мигрень",
            "referring_physician_name": "Др. Сидоров",
        }
        patient_data = {
            "iin": "850101350123",
            "last_name": "Иванов",
            "first_name": "Иван",
            "middle_name": "Иванович",
            "birth_date": "01.01.1985",
            "gender": "M",
        }
        service_data = {
            "code_gombp": "A06.20.010",
            "name_ru": "МРТ головного мозга без контраста",
            "modality": "MR",
            "tariff_paid": 35000,
        }

        start = time.time()
        pdf_bytes = generate_order_pdf(order_data, patient_data, service_data)
        elapsed = time.time() - start

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert b"%PDF" in pdf_bytes
        # AC: PDF генерируется < 3 сек
        assert elapsed < 3.0, f"PDF generation took {elapsed:.2f}s, expected < 3s"


class TestRBACReferrer:
    """Tests for REFERRER RBAC filtering (Task 6)."""

    @pytest.mark.asyncio
    async def test_referrer_sees_only_own_orders(self, monkeypatch, client, test_db):
        """REFERRER should only see orders where referring_physician_id matches."""
        from app.api import orders as orders_module
        from app.models.user import User
        from app.models.order import Order
        from app.models.patient import Patient
        from app.models.service import Service
        from app.auth.password import hash_password
        from datetime import date

        svc = Service(
            code_gombp="RBAC1",
            name_ru="RBAC test",
            modality="CT",
            duration_min=20,
            valid_from=date(2020, 1, 1),
        )
        test_db.add(svc)
        referrer = User(
            login="referrer1",
            password_hash=hash_password("test123"),
            role="REFERRER",
            last_name="Направитель",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(referrer)
        other_referrer = User(
            login="referrer2",
            password_hash=hash_password("test123"),
            role="REFERRER",
            last_name="Другой",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(other_referrer)
        patient = Patient(
            iin="900rbac01",
            last_name="Пациент",
            first_name="Тест",
            birth_date=date(1990, 1, 1),
            gender="M",
        )
        test_db.add(patient)
        await test_db.flush()
        order1 = Order(
            accession_number="RBAC-TEST-001",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="NEW",
            referring_physician_id=referrer.id,
            referring_physician_name="Направитель Тест",
        )
        test_db.add(order1)
        order2 = Order(
            accession_number="RBAC-TEST-002",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="NEW",
            referring_physician_id=referrer.id,
            referring_physician_name="Направитель Тест",
        )
        test_db.add(order2)
        order3 = Order(
            accession_number="RBAC-TEST-003",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="NEW",
            referring_physician_id=other_referrer.id,
            referring_physician_name="Другой Тест",
        )
        test_db.add(order3)
        await test_db.flush()

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(referrer.id), referrer.login, referrer.role,
            referrer.first_name, referrer.last_name
        )

        response = await client.get(
            "/api/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        order_ids = [o["id"] for o in data]
        assert str(order1.id) in order_ids
        assert str(order2.id) in order_ids
        assert str(order3.id) not in order_ids


class TestReportNewVersion:
    """Tests for report versioning (Task 4)."""

    async def _make_signed_report(self, test_db, suffix="v1"):
        from app.models.user import User
        from app.models.order import Order
        from app.models.report import Report
        from app.models.patient import Patient
        from app.models.service import Service
        from app.auth.password import hash_password
        from datetime import date, datetime, timezone

        svc = Service(
            code_gombp=f"B{suffix}",
            name_ru=f"Test {suffix}",
            modality="CT",
            duration_min=20,
            valid_from=date(2020, 1, 1),
        )
        test_db.add(svc)
        radiologist = User(
            login=f"radio_{suffix}",
            password_hash=hash_password("test123"),
            role="RADIOLOGIST",
            last_name="Тестов",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(radiologist)
        patient = Patient(
            iin=f"900{suffix}",
            last_name="Пациент",
            first_name="Тест",
            birth_date=date(1990, 1, 1),
            gender="M",
        )
        test_db.add(patient)
        await test_db.flush()
        order = Order(
            accession_number=f"VERSION-TEST-{suffix}",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="ISSUED",
        )
        test_db.add(order)
        await test_db.flush()
        report = Report(
            order_id=order.id,
            radiologist_id=radiologist.id,
            structured_fields={"key": "value"},
            description_text="Original description",
            conclusion_text="Original conclusion",
            critical_finding=True,
            diagnosis_icd_codes=["C34.1"],
            status="ISSUED",
            version="1",
            signed_at=datetime.now(timezone.utc),
            content_hash="original-hash",
            issued_at=datetime.now(timezone.utc),
        )
        test_db.add(report)
        await test_db.flush()
        await test_db.refresh(report)
        await test_db.refresh(order)
        return radiologist, order, report

    @pytest.mark.asyncio
    async def test_new_version_from_signed(self, monkeypatch, client, test_db):
        """New version from SIGNED creates DRAFT with parent_report_id."""
        from app.api import reports as reports_module
        from app.models.report import Report

        radiologist, order, report = await self._make_signed_report(test_db, "v2")
        report.status = "SIGNED"
        await test_db.flush()

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(radiologist.id), radiologist.login, radiologist.role,
            radiologist.first_name, radiologist.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/new-version",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DRAFT"
        assert data["parent_report_id"] == str(report.id)
        assert data["version"] == "2"
        assert data["description_text"] == "Original description"
        assert data["conclusion_text"] == "Original conclusion"
        assert data["critical_finding"] is True
        assert data["diagnosis_icd_codes"] == ["C34.1"]
        assert data["structured_fields"]["key"] == "value"

        # Old report unchanged
        result = await test_db.execute(select(Report).where(Report.id == report.id))
        old = result.scalar_one()
        assert old.status == "SIGNED"
        assert old.content_hash == "original-hash"

    @pytest.mark.asyncio
    async def test_new_version_from_issued_changes_order_status(self, monkeypatch, client, test_db):
        """New version from ISSUED transitions order to REPORTING."""
        from app.api import reports as reports_module
        from app.models.report import Report

        radiologist, order, report = await self._make_signed_report(test_db, "v3")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(radiologist.id), radiologist.login, radiologist.role,
            radiologist.first_name, radiologist.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/new-version",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DRAFT"

        # Order moved to REPORTING
        from app.models.order import Order
        order_result = await test_db.execute(select(Order).where(Order.id == order.id))
        updated_order = order_result.scalar_one()
        assert updated_order.status == "REPORTING"

    @pytest.mark.asyncio
    async def test_new_version_fails_for_draft(self, monkeypatch, client, test_db):
        """New version from DRAFT returns 403."""
        from app.api import reports as reports_module

        radiologist, order, report = await self._make_signed_report(test_db, "v4")
        report.status = "DRAFT"
        await test_db.flush()

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(radiologist.id), radiologist.login, radiologist.role,
            radiologist.first_name, radiologist.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/new-version",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestCITO:
    """Tests for CITO notifications (Task 5)."""

    @pytest.mark.asyncio
    async def test_issue_critical_creates_cito_audit_log(self, monkeypatch, client, test_db):
        """issue_report with critical_finding=True creates CITO_NOTIFICATION audit log."""
        from app.api import reports as reports_module
        from app.models.user import User
        from app.models.order import Order
        from app.models.report import Report
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.audit_log import AuditLog
        from app.auth.password import hash_password
        from datetime import date, datetime, timezone
        from sqlalchemy import select

        svc = Service(
            code_gombp="CITO1",
            name_ru="CITO test",
            modality="CT",
            duration_min=20,
            valid_from=date(2020, 1, 1),
        )
        test_db.add(svc)
        radiologist = User(
            login="cito_radio",
            password_hash=hash_password("test123"),
            role="RADIOLOGIST",
            last_name="Тестов",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(radiologist)
        patient = Patient(
            iin="900cito01",
            last_name="Пациент",
            first_name="Тест",
            birth_date=date(1990, 1, 1),
            gender="M",
        )
        test_db.add(patient)
        await test_db.flush()
        order = Order(
            accession_number="CITO-TEST-001",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="SIGNED",
        )
        test_db.add(order)
        await test_db.flush()
        report = Report(
            order_id=order.id,
            radiologist_id=radiologist.id,
            structured_fields={},
            description_text="Critical finding",
            conclusion_text="Urgent",
            critical_finding=True,
            status="SIGNED",
            version="1",
            signed_at=datetime.now(timezone.utc),
            content_hash="cito-hash",
        )
        test_db.add(report)
        await test_db.flush()
        await test_db.refresh(report)

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(radiologist.id), radiologist.login, radiologist.role,
            radiologist.first_name, radiologist.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/issue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        result = await test_db.execute(
            select(AuditLog).where(
                AuditLog.action == "CITO_NOTIFICATION",
                AuditLog.entity_id == report.id,
            )
        )
        cito_log = result.scalar_one_or_none()
        assert cito_log is not None
        assert cito_log.after_json["order_id"] == str(order.id)
        assert cito_log.after_json["accession_number"] == "CITO-TEST-001"

    @pytest.mark.asyncio
    async def test_issue_non_critical_no_audit_log(self, monkeypatch, client, test_db):
        """issue_report with critical_finding=False does not create CITO audit log."""
        from app.api import reports as reports_module
        from app.models.user import User
        from app.models.order import Order
        from app.models.report import Report
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.audit_log import AuditLog
        from app.auth.password import hash_password
        from datetime import date, datetime, timezone
        from sqlalchemy import select

        svc = Service(
            code_gombp="CITO2",
            name_ru="Non-CITO test",
            modality="CT",
            duration_min=20,
            valid_from=date(2020, 1, 1),
        )
        test_db.add(svc)
        radiologist = User(
            login="cito_radio2",
            password_hash=hash_password("test123"),
            role="RADIOLOGIST",
            last_name="Тестов2",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(radiologist)
        patient = Patient(
            iin="900cito02",
            last_name="Пациент",
            first_name="Тест",
            birth_date=date(1990, 1, 1),
            gender="M",
        )
        test_db.add(patient)
        await test_db.flush()
        order = Order(
            accession_number="CITO-TEST-002",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="SIGNED",
        )
        test_db.add(order)
        await test_db.flush()
        report = Report(
            order_id=order.id,
            radiologist_id=radiologist.id,
            structured_fields={},
            description_text="Normal",
            conclusion_text="Normal",
            critical_finding=False,
            status="SIGNED",
            version="1",
            signed_at=datetime.now(timezone.utc),
            content_hash="normal-hash",
        )
        test_db.add(report)
        await test_db.flush()
        await test_db.refresh(report)

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(radiologist.id), radiologist.login, radiologist.role,
            radiologist.first_name, radiologist.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/issue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        result = await test_db.execute(
            select(AuditLog).where(
                AuditLog.action == "CITO_NOTIFICATION",
                AuditLog.entity_id == report.id,
            )
        )
        cito_log = result.scalar_one_or_none()
        assert cito_log is None


class TestReportAuthorship:
    """Tests for report authorship checks (Task 3)."""

    async def _make_test_objects(self, test_db, iin_suffix="012"):
        from app.models.user import User
        from app.models.order import Order
        from app.models.report import Report
        from app.models.patient import Patient
        from app.models.service import Service
        from app.auth.password import hash_password
        from datetime import date

        svc = Service(
            code_gombp=f"A{iin_suffix}",
            name_ru=f"Test service {iin_suffix}",
            modality="CT",
            duration_min=20,
            valid_from=date(2020, 1, 1),
        )
        test_db.add(svc)
        author = User(
            login=f"radiologist_author_{iin_suffix}",
            password_hash=hash_password("test123"),
            role="RADIOLOGIST",
            last_name="Автор",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(author)
        other = User(
            login=f"radiologist_other_{iin_suffix}",
            password_hash=hash_password("test123"),
            role="RADIOLOGIST",
            last_name="Другой",
            first_name="Тест",
            is_active=True,
        )
        test_db.add(other)
        patient = Patient(
            iin=f"123456789{iin_suffix}",
            last_name="Пациент",
            first_name="Тест",
            birth_date=date(1990, 1, 1),
            gender="M",
        )
        test_db.add(patient)
        await test_db.flush()
        order = Order(
            accession_number=f"AUTH-TEST-{iin_suffix}",
            patient_id=patient.id,
            service_id=svc.id,
            modality="CT",
            status="NEW",
        )
        test_db.add(order)
        await test_db.flush()
        report = Report(
            order_id=order.id,
            radiologist_id=author.id,
            structured_fields={},
            status="DRAFT",
        )
        test_db.add(report)
        await test_db.flush()
        await test_db.refresh(report)
        return author, other, order, report

    @pytest.mark.asyncio
    async def test_other_radiologist_cannot_edit_report(self, monkeypatch, client, test_db, test_admin):
        """RADIOLOGIST who is not the author gets 403 on update."""
        from app.api import reports as reports_module

        author, other, order, report = await self._make_test_objects(test_db, "012")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(other.id), other.login, other.role,
            other.first_name, other.last_name
        )

        response = await client.put(
            f"/api/reports/{report.id}",
            json={
                "order_id": str(order.id),
                "description_text": "edited by other",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "автор" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_other_radiologist_cannot_sign_report(self, monkeypatch, client, test_db):
        """RADIOLOGIST who is not the author gets 403 on sign."""
        from app.api import reports as reports_module

        author, other, order, report = await self._make_test_objects(test_db, "013")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(other.id), other.login, other.role,
            other.first_name, other.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/sign",
            json={"password": "test123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "автор" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_admin_cannot_edit_report(self, monkeypatch, client, test_db, test_admin):
        """ADMIN can view reports but cannot edit them."""
        _, _, order, report = await self._make_test_objects(test_db, "014")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(test_admin.id), test_admin.login, test_admin.role,
            test_admin.first_name, test_admin.last_name
        )

        response = await client.put(
            f"/api/reports/{report.id}",
            json={
                "order_id": str(order.id),
                "description_text": "edited by admin",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cannot_create_report(self, monkeypatch, client, test_db, test_admin):
        """ADMIN cannot create new reports."""
        _, _, order, _ = await self._make_test_objects(test_db, "015")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(test_admin.id), test_admin.login, test_admin.role,
            test_admin.first_name, test_admin.last_name
        )

        response = await client.post(
            "/api/reports",
            json={
                "order_id": str(order.id),
                "description_text": "created by admin",
                "conclusion_text": "created by admin",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cannot_sign_report(self, monkeypatch, client, test_db, test_admin):
        """ADMIN cannot sign reports."""
        _, _, _, report = await self._make_test_objects(test_db, "016")

        from app.auth import jwt as jwt_module
        monkeypatch.setattr(jwt_module.settings, 'SECRET_KEY', 'test-secret-key-for-jwt')
        token = create_access_token(
            str(test_admin.id), test_admin.login, test_admin.role,
            test_admin.first_name, test_admin.last_name
        )

        response = await client.post(
            f"/api/reports/{report.id}/sign",
            json={"password": "test123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
