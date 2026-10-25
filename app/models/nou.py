# app/models/nou.py
"""
Model for the external forecast database.

Uses its own declarative base so the table is never registered on the
main application metadata (and therefore never created by
``Base.metadata.create_all``).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings


class ForecastBase(DeclarativeBase):
    """Declarative base bound to the external forecast database."""


class ForecastHexHourly(ForecastBase):
    __tablename__ = "forecast_hex_hourly"
    __table_args__ = {"schema": settings.FORECAST_DB_SCHEMA}

    # Composite key only exists for the ORM identity map; reads do not
    # depend on the real table's constraint.
    hex_id: Mapped[str] = mapped_column(String, primary_key=True)
    target_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    predicted_user_count: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
