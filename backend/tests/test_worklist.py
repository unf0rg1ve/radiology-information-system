"""
Tests for worklist endpoints.
"""
import pytest
from datetime import date

from app.models.user import User
from app.models.order import Order
from app.models.patient import Patient
from app.models.service import Service
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


async def _make_worklist_order(test_db, suffix: str, status: str):
    svc = Service(
        code_gombp=f"WL{suffix}",
        name_ru=f"Тестовая услуга {suffix}",
        modality="CT",
        duration_min=20,
        valid_from=date(2020, 1, 1),
    )
    test_db.add(svc)

    patient = Patient(
        iin=f"900wl{suffix.zfill(6)}",
        last_name="Пациент",
        first_name=suffix,
        birth_date=date(1990, 1, 1),
        gender="M",
    )
    test_db.add(patient)
    await test_db.flush()

    order = Order(
        accession_number=f"WL-{suffix}",
        patient_id=patient.id,
        service_id=svc.id,
        modality="CT",
        status=status,
    )
    test_db.add(order)
    await test_db.flush()
    return order


async def _make_user(test_db, login: str, role: str):
    user = User(
        login=login,
        password_hash=hash_password("test123"),
        role=role,
        last_name=role,
        first_name="Тест",
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()
    return user


def _token_for(user):
    return create_access_token(
        str(user.id), user.login, user.role,
        user.first_name, user.last_name
    )


@pytest.mark.asyncio
async def test_registrar_can_mark_arrived(client, test_db, monkeypatch):
    """REGISTRAR should be able to mark a scheduled order as ARRIVED (F4.2)."""
    svc = Service(
        code_gombp="WL001",
        name_ru="Тестовая услуга",
        modality="CT",
        duration_min=20,
        valid_from=date(2020, 1, 1),
    )
    test_db.add(svc)

    registrar = User(
        login="registrar_arrived",
        password_hash=hash_password("test123"),
        role="REGISTRAR",
        last_name="Регистратор",
        first_name="Тест",
        is_active=True,
    )
    test_db.add(registrar)

    patient = Patient(
        iin="900wl000001",
        last_name="Пациент",
        first_name="Тест",
        birth_date=date(1990, 1, 1),
        gender="M",
    )
    test_db.add(patient)
    await test_db.flush()

    order = Order(
        accession_number="WL-ARRIVED-001",
        patient_id=patient.id,
        service_id=svc.id,
        modality="CT",
        status="SCHEDULED",
    )
    test_db.add(order)
    await test_db.flush()

    from app.auth import jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SECRET_KEY", "test-secret-key-for-jwt")
    token = create_access_token(
        str(registrar.id), registrar.login, registrar.role,
        registrar.first_name, registrar.last_name
    )

    response = await client.post(
        f"/api/worklist/{order.id}/arrived",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ARRIVED"


@pytest.mark.asyncio
async def test_technologist_can_run_arrived_order(client, test_db, monkeypatch):
    order = await _make_worklist_order(test_db, "TECH001", "ARRIVED")
    technologist = await _make_user(test_db, "technologist_progress", "TECHNOLOGIST")

    from app.auth import jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SECRET_KEY", "test-secret-key-for-jwt")

    response = await client.post(
        f"/api/worklist/{order.id}/in-progress",
        headers={"Authorization": f"Bearer {_token_for(technologist)}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_radiologist_cannot_mark_arrived(client, test_db, monkeypatch):
    order = await _make_worklist_order(test_db, "RAD001", "SCHEDULED")
    radiologist = await _make_user(test_db, "radiologist_arrived_forbidden", "RADIOLOGIST")

    from app.auth import jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SECRET_KEY", "test-secret-key-for-jwt")

    response = await client.post(
        f"/api/worklist/{order.id}/arrived",
        headers={"Authorization": f"Bearer {_token_for(radiologist)}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_radiologist_worklist_defaults_to_reports(client, test_db, monkeypatch):
    scheduled = await _make_worklist_order(test_db, "RAD002", "SCHEDULED")
    to_report = await _make_worklist_order(test_db, "RAD003", "TO_REPORT")
    radiologist = await _make_user(test_db, "radiologist_worklist", "RADIOLOGIST")

    from app.auth import jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SECRET_KEY", "test-secret-key-for-jwt")

    response = await client.get(
        "/api/worklist",
        headers={"Authorization": f"Bearer {_token_for(radiologist)}"},
    )

    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert str(to_report.id) in ids
    assert str(scheduled.id) not in ids
