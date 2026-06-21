"""Tests for patients API and IIN validation."""
import pytest

from app.schemas.patient import PatientBase


def _make_valid_iin():
    """Return a valid Kazakhstan IIN (checksum is correct)."""
    # 21-02-03-3-4506-7 -> 1903-02-21, control digit 7
    return "210203345067"


@pytest.mark.asyncio
async def test_create_patient_with_valid_iin(client, auth_headers):
    """Patient creation with a valid IIN should succeed (F1.2)."""
    response = await client.post("/api/patients", headers=auth_headers, json={
        "iin": _make_valid_iin(),
        "last_name": "Тестов",
        "first_name": "Аудит",
        "middle_name": "Пациентович",
        "birth_date": "1903-02-21",
        "gender": "M",
        "phone": "+77001112233",
        "benefit_category": "NONE",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["iin"] == _make_valid_iin()
    assert data["last_name"] == "Тестов"


@pytest.mark.asyncio
async def test_create_patient_with_invalid_iin_rejected(client, auth_headers):
    """Non-digit IIN should be rejected with 422 (F1.2)."""
    response = await client.post("/api/patients", headers=auth_headers, json={
        "iin": "21020334506A",
        "last_name": "Тестов",
        "first_name": "Аудит",
        "middle_name": "Пациентович",
        "birth_date": "1903-02-21",
        "gender": "M",
        "phone": "+77001112233",
        "benefit_category": "NONE",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_patient_with_wrong_control_digit_rejected(client, auth_headers):
    """IIN with wrong control digit should be rejected (F1.2)."""
    response = await client.post("/api/patients", headers=auth_headers, json={
        "iin": "210203345060",  # last digit should be 7
        "last_name": "Тестов",
        "first_name": "Аудит",
        "middle_name": "Пациентович",
        "birth_date": "1903-02-21",
        "gender": "M",
        "phone": "+77001112233",
        "benefit_category": "NONE",
    })
    assert response.status_code == 422


def test_patient_base_iin_regex_accepts_digits():
    """Unit test for schema-level IIN regex validation."""
    patient = PatientBase(
        iin=_make_valid_iin(),
        last_name="Тестов",
        first_name="Аудит",
        birth_date="1903-02-21",
        gender="M",
    )
    assert patient.iin == _make_valid_iin()
