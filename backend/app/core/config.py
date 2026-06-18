"""
CRM Unificado EPEM — Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# El .env esta en la raiz del proyecto, tres niveles arriba de app/core/config.py
# (config.py -> core -> app -> backend -> crm-unificado)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    # App
    APP_NAME: str = "CRM Unificado EPEM"
    DEBUG: bool = os.getenv("FASTAPI_DEBUG", "false").lower() == "true"

    # PostgreSQL DW
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "crm_epem")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "crm_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "crm_secure_2026")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    # EPEM MySQL (source)
    EPEM_DB_HOST: str = os.getenv("EPEM_DB_HOST", "192.168.0.250")
    EPEM_DB_PORT: int = int(os.getenv("EPEM_DB_PORT", "3306"))
    EPEM_DB_USER: str = os.getenv("EPEM_DB_USER", "root")
    EPEM_DB_PASSWORD: str = os.getenv("EPEM_DB_PASSWORD", "epem2022")
    EPEM_DB_NAME: str = os.getenv("EPEM_DB_NAME", "copy_epem_system")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "crm-jwt-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))

    # ETL
    SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))


settings = Settings()
