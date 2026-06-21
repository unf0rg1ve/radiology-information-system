from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import io
from app.core.database import get_db
from app.auth.rbac import any_authenticated, head_only, admin_only
from app.schemas.auth import UserMe
from app.models.order import Order, OrderStatus
from app.models.report import Report
from app.models.device import Device
from app.models.user import User
from app.models.study import Study
from app.models.appointment import Appointment
from app.core.utils import utc_now

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/dashboard")
async def dashboard(
    period: str = Query("today", pattern="^(today|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(any_authenticated),
):
    now = utc_now()
    if period == "today":
        start_date = now.date()
    elif period == "week":
        start_date = (now - timedelta(days=7)).date()
    else:
        start_date = (now - timedelta(days=30)).date()

    # Total studies
    result = await db.execute(
        select(func.count(Order.id)).where(func.date(Order.created_at) >= start_date)
    )
    total_studies = result.scalar() or 0

    # By status
    result = await db.execute(
        select(Order.status, func.count(Order.id))
        .where(func.date(Order.created_at) >= start_date)
        .group_by(Order.status)
    )
    by_status = {(row[0].value if row[0] else None): row[1] for row in result.all()}

    # By modality
    result = await db.execute(
        select(Order.modality, func.count(Order.id))
        .where(func.date(Order.created_at) >= start_date)
        .group_by(Order.modality)
    )
    by_modality = {row[0]: row[1] for row in result.all()}

    # By financing type (ТЗ F8.5)
    result = await db.execute(
        select(Order.financing_type, func.count(Order.id))
        .where(func.date(Order.created_at) >= start_date)
        .group_by(Order.financing_type)
    )
    by_financing = {row[0]: row[1] for row in result.all()}

    # By doctor (ТЗ F8.1, F8.3)
    result = await db.execute(
        select(
            User.last_name,
            User.first_name,
            func.count(Order.id).label("count"),
        )
        .select_from(Order)
        .join(Report, Order.id == Report.order_id, isouter=True)
        .join(User, Report.radiologist_id == User.id, isouter=True)
        .where(func.date(Order.created_at) >= start_date)
        .group_by(User.id, User.last_name, User.first_name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
    )
    by_doctor = [
        {"name": f"{row.last_name} {row.first_name}" if row.last_name else "Не назначен", "count": row.count}
        for row in result.all()
    ]

    # By device (ТЗ F8.1, F8.3)
    result = await db.execute(
        select(
            Device.name,
            Device.modality_type,
            func.count(Appointment.id).label("count"),
        )
        .select_from(Appointment)
        .join(Device, Appointment.device_id == Device.id, isouter=True)
        .join(Order, Appointment.order_id == Order.id, isouter=True)
        .where(func.date(Order.created_at) >= start_date)
        .group_by(Device.id, Device.name, Device.modality_type)
        .order_by(func.count(Appointment.id).desc())
    )
    by_device = [
        {"name": row.name or "Неизвестно", "modality": row.modality_type, "count": row.count}
        for row in result.all()
    ]

    # Average TAT
    result = await db.execute(
        select(
            func.avg(
                func.extract('epoch', Report.issued_at - Order.created_at) / 60
            )
        )
        .select_from(Order)
        .join(Report, Order.id == Report.order_id)
        .where(
            and_(
                func.date(Order.created_at) >= start_date,
                Report.status == "ISSUED",
                Report.issued_at != None,
            )
        )
    )
    avg_tat_minutes = result.scalar() or 0
    avg_tat_hours = round(avg_tat_minutes / 60, 1) if avg_tat_minutes else 0

    # Overdue count (TAT > 4 hours)
    result = await db.execute(
        select(func.count(Order.id))
        .select_from(Order)
        .join(Report, Order.id == Report.order_id)
        .where(
            and_(
                func.date(Order.created_at) >= start_date,
                Report.status == "ISSUED",
                func.extract('epoch', Report.issued_at - Order.created_at) > 4 * 3600,
            )
        )
    )
    overdue_count = result.scalar() or 0

    return {
        "period": period,
        "total_studies": total_studies,
        "by_status": by_status,
        "by_modality": by_modality,
        "by_financing": by_financing,
        "by_doctor": by_doctor,
        "by_device": by_device,
        "avg_tat_hours": avg_tat_hours,
        "overdue_count": overdue_count,
        "to_report": by_status.get("TO_REPORT", 0),
    }


@router.get("/turnaround")
async def turnaround_stats(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(head_only),
):
    result = await db.execute(
        select(
            func.date(Order.created_at).label("date"),
            func.count(Order.id).label("count"),
            func.avg(
                func.extract('epoch', Report.issued_at - Order.created_at) / 60
            ).label("avg_tat_minutes"),
        )
        .select_from(Order)
        .join(Report, Order.id == Report.order_id)
        .where(
            and_(
                func.date(Order.created_at) >= from_date,
                func.date(Order.created_at) <= to_date,
                Report.status == "ISSUED",
            )
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )

    data = []
    for row in result.all():
        data.append({
            "date": row.date.isoformat() if row.date else None,
            "count": row.count,
            "avg_tat_hours": round(row.avg_tat_minutes / 60, 1) if row.avg_tat_minutes else 0,
        })

    return {"period": {"from": from_date.isoformat(), "to": to_date.isoformat()}, "data": data}


@router.get("/export")
async def export_stats(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    from_date: date = Query(None),
    to_date: date = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserMe = Depends(head_only),
):
    """Выгрузка статистики в CSV/Excel (ТЗ F8.4)."""
    query = (
        select(
            Order.accession_number,
            Order.modality,
            Order.body_part,
            Order.priority,
            Order.financing_type,
            Order.status,
            Order.created_at,
            Report.issued_at,
            Report.signed_at,
            Report.critical_finding,
        )
        .select_from(Order)
        .outerjoin(Report, Order.id == Report.order_id)
        .order_by(Order.created_at.desc())
    )

    if from_date:
        query = query.where(func.date(Order.created_at) >= from_date)
    if to_date:
        query = query.where(func.date(Order.created_at) <= to_date)

    result = await db.execute(query)
    rows = result.all()

    data = []
    for row in rows:
        tat_hours = None
        if row.issued_at and row.created_at:
            tat_hours = round((row.issued_at - row.created_at).total_seconds() / 3600, 1)

        data.append({
            "Accession Number": row.accession_number,
            "Модальность": row.modality,
            "Область": row.body_part or "",
            "Приоритет": row.priority,
            "Финансирование": row.financing_type,
            "Статус": row.status,
            "Дата создания": row.created_at.strftime("%d.%m.%Y %H:%M") if row.created_at else "",
            "Дата выдачи": row.issued_at.strftime("%d.%m.%Y %H:%M") if row.issued_at else "",
            "TAT (часы)": tat_hours if tat_hours is not None else "",
            "Критическая находка": "Да" if row.critical_finding else "Нет",
        })

    df = pd.DataFrame(data)

    if format == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False, encoding="utf-8-sig")
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ris-stats.csv"},
        )
    else:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Статистика")
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=ris-stats.xlsx"},
        )
