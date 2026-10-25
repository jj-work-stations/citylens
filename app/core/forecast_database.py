# app/core/forecast_database.py
"""
Separate (read-only) engine for the external forecast database.

The forecast data lives in another Postgres instance, so it must not
share ``Base.metadata`` / ``engine`` with the main application database.
"""
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

forecast_engine = create_async_engine(
    settings.forecast_database_url,
    echo=False,
    pool_size=settings.FORECAST_DB_POOL_SIZE,
    max_overflow=settings.FORECAST_DB_MAX_OVERFLOW,
    pool_pre_ping=True,     # external DB may drop idle connections
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={
        # Fail fast when the remote host is unreachable instead of
        # hanging until the gateway returns a 504.
        "timeout": settings.FORECAST_DB_CONNECT_TIMEOUT,
        "server_settings": {
            "application_name": "map-api-forecast",
            # Never let a single query occupy a worker for minutes.
            "statement_timeout": str(settings.FORECAST_DB_STATEMENT_TIMEOUT_MS),
        },
    },
)

ForecastSessionLocal = async_sessionmaker(
    bind=forecast_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_forecast_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session on the forecast database."""
    async with ForecastSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
