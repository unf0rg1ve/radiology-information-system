import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "RIS MVP"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://ris:ris@db:5432/ris"

    ORTHANC_URL: str = "http://orthanc:8042"
    ORTHANC_EXTERNAL_URL: str = "http://10.177.134.96:8042"
    ORTHANC_USER: str = "orthanc"
    ORTHANC_PASSWORD: str = "orthanc"

    CORS_ORIGINS: list[str] = ["http://10.177.134.96:3000", "http://localhost:3000", "http://localhost:5173"]

    WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

    DEFAULT_ORG_NAME: str = "Диагностический центр"
    DEFAULT_ORG_LICENSE: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
