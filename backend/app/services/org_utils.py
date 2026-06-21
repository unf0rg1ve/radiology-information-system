from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization


async def _get_org_data(db: AsyncSession, org_id=None) -> dict | None:
    """Load organization data for PDF headers.
    First tries the specified org_id, then falls back to the first org in DB.
    """
    if org_id:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one_or_none()
        if org:
            return {
                "name": org.name_ru or "",
                "license": org.license_number or "",
                "address": org.address or "",
                "phone": org.phone or "",
            }

    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if org:
        return {
            "name": org.name_ru or "",
            "license": org.license_number or "",
            "address": org.address or "",
            "phone": org.phone or "",
        }

    return None
