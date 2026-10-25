# app/core/config.py
from functools import lru_cache
from typing import List
from urllib.parse import quote_plus
import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "Map Platform"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    # ── Forecast DB (external, read-only) ─────────────────────
    # If FORECAST_DATABASE_URL is set it wins; otherwise the URL is
    # built from the individual parts below.
    FORECAST_DATABASE_URL: str = ""
    FORECAST_DB_HOST: str = "127.0.0.1"
    FORECAST_DB_PORT: int = 5432
    FORECAST_DB_USER: str = "postgres"
    FORECAST_DB_PASSWORD: str = ""
    FORECAST_DB_NAME: str = "postgres"
    FORECAST_DB_SCHEMA: str = "forecast"
    FORECAST_DB_POOL_SIZE: int = 5
    FORECAST_DB_MAX_OVERFLOW: int = 5
    FORECAST_DB_CONNECT_TIMEOUT: int = 10        # seconds
    FORECAST_DB_STATEMENT_TIMEOUT_MS: int = 15000
    FORECAST_DB_COUNT_TIMEOUT_MS: int = 60000    # only for include_total=true

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT ───────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost"]

    # ── External black-box services ───────────────────────────
    SERVICE1_URL: str = "http://service1:8001"
    SERVICE2_URL: str = "http://service2:8002"
    SERVICE3_URL: str = "http://service3:8003"
    SERVICE4_URL: str = "http://service4:8004"
    SERVICE_TIMEOUT: int = 30

    # ── Pagination ────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    LOKI_URL: str = "http://loki:3100"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def forecast_database_url(self) -> str:
        if self.FORECAST_DATABASE_URL:
            return self.FORECAST_DATABASE_URL
        return (
            "postgresql+asyncpg://"
            f"{quote_plus(self.FORECAST_DB_USER)}:{quote_plus(self.FORECAST_DB_PASSWORD)}"
            f"@{self.FORECAST_DB_HOST}:{self.FORECAST_DB_PORT}/"
            f"{self.FORECAST_DB_NAME}"
        )

    @property
    def service_urls(self) -> dict[str, str]:
        return {
            "service1": self.SERVICE1_URL,
            "service2": self.SERVICE2_URL,
            "service3": self.SERVICE3_URL,
            "service4": self.SERVICE4_URL,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()