from app.api.auth import router as auth_router
from app.api.patients import router as patients_router
from app.api.orders import router as orders_router
from app.api.reports import router as reports_router
from app.api.refs import router as refs_router
from app.api.schedule import router as schedule_router
from app.api.worklist import router as worklist_router
from app.api.stats import router as stats_router
from app.api.admin import router as admin_router
from app.api.webhook import router as webhook_router
from app.api.notifications import router as notifications_router
from app.api.dicom import router as dicom_router

__all__ = [
    "auth_router",
    "patients_router",
    "orders_router",
    "reports_router",
    "refs_router",
    "schedule_router",
    "worklist_router",
    "stats_router",
    "admin_router",
    "webhook_router",
    "notifications_router",
    "dicom_router",
]
