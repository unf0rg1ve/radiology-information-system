from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.database import engine, AsyncSessionLocal
from app.api import (
    auth_router, patients_router, orders_router, reports_router,
    refs_router, schedule_router, worklist_router, stats_router, admin_router,
    webhook_router, notifications_router, dicom_router,
)
from app.api.pdf_endpoints import router as pdf_router
from app.api.ws import router as ws_router
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматический аудит через SQLAlchemy event listeners на AsyncSession
    # не работает (события диспатчатся на sync_session). Аудит реализован
    # явными AuditLog(...) записями в API-эндпоинтах. См. ARCHITECTURE_DECISIONS.md F7.3.
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Радиологическая информационная система (RIS) MVP для Республики Казахстан",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Webhook-Secret"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(refs_router, prefix="/api")
app.include_router(schedule_router, prefix="/api")
app.include_router(worklist_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(dicom_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
