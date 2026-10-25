# app/models/poi_agg.py
"""
Model for POI aggregated data from the external forecast database.
"""
from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.nou import ForecastBase


class PoiAgg(ForecastBase):
    __tablename__ = "poi_agg"
    __table_args__ = {"schema": "public"}

    hex_id: Mapped[str] = mapped_column(String, primary_key=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
