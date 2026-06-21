"""
PDF API endpoints (F2.5, F5.6).
- GET /api/orders/{id}/pdf — PDF направления
"""
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.auth.rbac import any_authenticated
from app.schemas.auth import UserMe
from app.models.order import Order
from app.services.pdf import generate_order_pdf
from app.services.org_utils import _get_org_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pdf", tags=["PDF"])


@router.get("/orders/{order_id}")
async def get_order_pdf(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    """PDF направления на исследование."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Направление не найдено")

    org_data = await _get_org_data(db, order.org_id)

    order_data = {
        "accession_number": order.accession_number,
        "status": order.status,
        "priority": order.priority,
        "financing_type": order.financing_type,
        "modality": order.modality,
        "body_part": order.body_part,
        "clinical_notes": order.clinical_notes,
        "contrast_agent": order.contrast_agent,
        "created_at": order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "",
        "diagnosis_icd_name": order.diagnosis_icd.name_ru if order.diagnosis_icd else None,
        "referring_physician_name": order.referring_physician_name,
    }

    patient_data = {}
    if order.patient:
        patient_data = {
            "iin": order.patient.iin,
            "last_name": order.patient.last_name,
            "first_name": order.patient.first_name,
            "middle_name": order.patient.middle_name,
            "birth_date": order.patient.birth_date.strftime("%d.%m.%Y") if order.patient.birth_date else "",
            "gender": order.patient.gender,
        }

    service_data = {}
    if order.service:
        service_data = {
            "code_gombp": order.service.code_gombp,
            "name_ru": order.service.name_ru,
            "modality": order.service.modality,
            "tariff_paid": float(order.service.tariff_paid) if order.service.tariff_paid else 0,
        }

    try:
        pdf_bytes = generate_order_pdf(order_data, patient_data, service_data, org_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=order_{order.accession_number}.pdf"
            },
        )
    except Exception as e:
        logger.error(f"PDF generation failed for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF: {str(e)}")
