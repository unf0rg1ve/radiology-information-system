"""
PDF-генерация (F2.5, F5.6) с помощью WeasyPrint.
- GET /api/orders/{id}/pdf — направление
- GET /api/reports/{id}/pdf — заключение

Обязательные реквизиты:
  Организация (название, лицензия МЗ РК)
  ИИН пациента
  Код услуги
  МКБ-10
  Accession Number
  Дата

Для заключения дополнительно:
  Текст описания/заключения
  ФИО и подпись врача
  SHA-256 хэш
  Водяной знак "ЧЕРНОВИК" для status=DRAFT
  Красный штамп "КРИТИЧЕСКАЯ НАХОДКА" при critical_finding=true
"""
import logging
import os
from io import BytesIO
from uuid import UUID
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

def _priority_name(val):
    return {"ROUTINE": "Плановый", "URGENT": "Срочный"}.get(val, val)

def _financing_name(val):
    return {"GOMBP": "ГОБМП", "OSMS": "ОСМС", "PAID": "Платно"}.get(val, val)

def _status_name(val):
    if not val:
        return val
    return {
        "NEW": "Новый", "SCHEDULED": "Запланирован",
        "ARRIVED": "Прибыл", "IN_PROGRESS": "В работе",
        "ACQUIRED": "Снимки получены", "TO_REPORT": "К описанию",
        "REPORTING": "Описывается", "SIGNED": "Подписано",
        "ISSUED": "Выдано", "CANCELLED": "Отменён",
        "DRAFT": "Черновик",
    }.get(val, val)

def _gender_name(val):
    return {"M": "Мужской", "F": "Женский"}.get(val, val)

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
)
jinja_env.filters["priority_name"] = _priority_name
jinja_env.filters["financing_name"] = _financing_name
jinja_env.filters["status_name"] = _status_name
jinja_env.filters["gender_name"] = _gender_name


def _get_org_info() -> dict:
    """Get default organization info for PDF headers."""
    return {
        "name": "Диагностический центр",
        "license": "Лицензия МЗ РК № 00000",
        "address": "г. Алматы, пр. Назарбаева, 1",
        "phone": "+7 (727) 123-45-67",
    }


def generate_order_pdf(
    order_data: dict,
    patient_data: dict,
    service_data: dict,
    org_data: dict | None = None,
) -> bytes:
    """
    Генерация PDF направления на исследование.

    Args:
        order_data: {accession_number, status, priority, financing_type, modality, body_part, clinical_notes, created_at}
        patient_data: {iin, last_name, first_name, middle_name, birth_date, gender}
        service_data: {code_gombp, name_ru, modality, tariff_paid}
        org_data: {name, license, address, phone}

    Returns:
        PDF bytes
    """
    if org_data is None:
        org_data = _get_org_info()

    template = jinja_env.get_template("order_pdf.html")
    html_content = template.render(
        org=org_data,
        order=order_data,
        patient=patient_data,
        service=service_data,
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
        is_draft=order_data.get("status") == "DRAFT",
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


def generate_report_pdf(
    report_data: dict,
    order_data: dict,
    patient_data: dict,
    service_data: dict,
    radiologist_data: dict,
    org_data: dict | None = None,
) -> bytes:
    """
    Генерация PDF медицинского заключения.

    Args:
        report_data: {status, description_text, conclusion_text, critical_finding, diagnosis_icd_codes, content_hash, signed_at, version}
        order_data: {accession_number, priority, financing_type, modality, body_part, clinical_notes, created_at}
        patient_data: {iin, last_name, first_name, middle_name, birth_date, gender}
        service_data: {code_gombp, name_ru}
        radiologist_data: {last_name, first_name, middle_name, specialization, license_number}
        org_data: {name, license, address, phone}

    Returns:
        PDF bytes
    """
    if org_data is None:
        org_data = _get_org_info()

    template = jinja_env.get_template("report_pdf.html")
    html_content = template.render(
        org=org_data,
        report=report_data,
        order=order_data,
        patient=patient_data,
        service=service_data,
        radiologist=radiologist_data,
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
        is_draft=report_data.get("status") == "DRAFT",
        is_critical=report_data.get("critical_finding", False),
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
