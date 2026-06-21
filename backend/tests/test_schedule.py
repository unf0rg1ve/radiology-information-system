from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.auth.jwt import create_access_token
from app.models.appointment import Appointment
from app.models.device import Device
from app.models.order import Order, OrderStatus
from app.models.patient import Patient
from app.models.service import Service
from app.core.utils import utc_now


@pytest.mark.asyncio
async def test_registrar_can_create_appointment_from_json_body(monkeypatch, client, test_db, test_registrar):
    """Frontend sends appointment fields as JSON body, not query params."""
    from app.auth import jwt as jwt_module
    from app.api import schedule as schedule_module

    async def noop_publish_mwl(**kwargs):
        return None

    monkeypatch.setattr(jwt_module.settings, "SECRET_KEY", "test-secret-key-for-jwt")
    monkeypatch.setattr(schedule_module.orthanc_adapter, "publish_mwl", noop_publish_mwl)

    service = Service(
        code_gombp="SCH-001",
        name_ru="КТ тест",
        modality="CT",
        duration_min=20,
        valid_from=date(2020, 1, 1),
    )
    patient = Patient(
        iin="900101300001",
        last_name="Пациент",
        first_name="Тест",
        birth_date=date(1990, 1, 1),
        gender="M",
    )
    device = Device(
        name="КТ-1",
        modality_type="CT",
        ae_title="CT_SCH_1",
        status="ACTIVE",
    )
    test_db.add_all([service, patient, device])
    await test_db.flush()

    order = Order(
        accession_number="SCH-0001",
        patient_id=patient.id,
        service_id=service.id,
        modality="CT",
        status=OrderStatus.NEW,
        created_by=test_registrar.id,
    )
    test_db.add(order)
    await test_db.flush()

    token = create_access_token(
        str(test_registrar.id),
        test_registrar.login,
        test_registrar.role,
        test_registrar.first_name,
        test_registrar.last_name,
    )

    slot_start = (utc_now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(minutes=30)

    response = await client.post(
        "/api/schedule/appointments",
        json={
            "order_id": str(order.id),
            "device_id": str(device.id),
            "slot_start": slot_start.isoformat(),
            "slot_end": slot_end.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == OrderStatus.SCHEDULED.value

    appointment = (
        await test_db.execute(select(Appointment).where(Appointment.order_id == order.id))
    ).scalar_one()
    assert appointment.device_id == device.id
    assert appointment.slot_start == slot_start
    assert appointment.slot_end == slot_start + timedelta(minutes=20)

    await test_db.refresh(order)
    assert order.status == OrderStatus.SCHEDULED

    slots_response = await client.get(
        "/api/schedule/slots",
        params={"device_id": str(device.id), "date": slot_start.date().isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert slots_response.status_code == 200
    occupied_slots = [slot for slot in slots_response.json()["slots"] if slot["occupied"]]
    assert len(occupied_slots) == 1
    assert occupied_slots[0]["appointment"]["accession_number"] == order.accession_number
    assert occupied_slots[0]["appointment"]["patient_name"] == "Пациент Тест"


@pytest.mark.asyncio
async def test_registrar_cannot_create_appointment_in_past(client, test_db, test_registrar):
    service = Service(
        code_gombp="SCH-002",
        name_ru="КТ тест 2",
        modality="CT",
        duration_min=20,
        valid_from=date(2020, 1, 1),
    )
    patient = Patient(
        iin="900101300002",
        last_name="Пациент",
        first_name="Прошлый",
        birth_date=date(1990, 1, 1),
        gender="M",
    )
    device = Device(
        name="КТ-2",
        modality_type="CT",
        ae_title="CT_SCH_2",
        status="ACTIVE",
    )
    test_db.add_all([service, patient, device])
    await test_db.flush()

    order = Order(
        accession_number="SCH-0002",
        patient_id=patient.id,
        service_id=service.id,
        modality="CT",
        status=OrderStatus.NEW,
        created_by=test_registrar.id,
    )
    test_db.add(order)
    await test_db.flush()

    token = create_access_token(
        str(test_registrar.id),
        test_registrar.login,
        test_registrar.role,
        test_registrar.first_name,
        test_registrar.last_name,
    )
    slot_start = utc_now() - timedelta(days=1)

    response = await client.post(
        "/api/schedule/appointments",
        json={
            "order_id": str(order.id),
            "device_id": str(device.id),
            "slot_start": slot_start.isoformat(),
            "slot_end": (slot_start + timedelta(minutes=30)).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert "прошедшее" in response.json()["detail"]


@pytest.mark.asyncio
async def test_registrar_can_cancel_appointment(monkeypatch, client, test_db, test_registrar):
    from app.api import schedule as schedule_module

    async def noop_publish_mwl(**kwargs):
        return None

    monkeypatch.setattr(schedule_module.orthanc_adapter, "publish_mwl", noop_publish_mwl)

    service = Service(
        code_gombp="SCH-003",
        name_ru="КТ тест 3",
        modality="CT",
        duration_min=20,
        valid_from=date(2020, 1, 1),
    )
    patient = Patient(
        iin="900101300003",
        last_name="Пациент",
        first_name="Отмена",
        birth_date=date(1990, 1, 1),
        gender="M",
    )
    device = Device(
        name="КТ-3",
        modality_type="CT",
        ae_title="CT_SCH_3",
        status="ACTIVE",
    )
    test_db.add_all([service, patient, device])
    await test_db.flush()

    order = Order(
        accession_number="SCH-0003",
        patient_id=patient.id,
        service_id=service.id,
        modality="CT",
        status=OrderStatus.NEW,
        created_by=test_registrar.id,
    )
    test_db.add(order)
    await test_db.flush()

    token = create_access_token(
        str(test_registrar.id),
        test_registrar.login,
        test_registrar.role,
        test_registrar.first_name,
        test_registrar.last_name,
    )
    slot_start = (utc_now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)

    create_response = await client.post(
        "/api/schedule/appointments",
        json={
            "order_id": str(order.id),
            "device_id": str(device.id),
            "slot_start": slot_start.isoformat(),
            "slot_end": (slot_start + timedelta(minutes=30)).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 200

    appointment = (
        await test_db.execute(select(Appointment).where(Appointment.order_id == order.id))
    ).scalar_one()

    cancel_response = await client.delete(
        f"/api/schedule/appointments/{appointment.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    remaining = (
        await test_db.execute(select(Appointment).where(Appointment.id == appointment.id))
    ).scalar_one_or_none()
    assert remaining is None

    await test_db.refresh(order)
    assert order.status == OrderStatus.NEW
