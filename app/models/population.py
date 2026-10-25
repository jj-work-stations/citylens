# app/models/population.py
from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Index, Integer, Numeric, Column
from sqlalchemy.orm import DeclarativeBase

from app.core.database import Base


def make_population_model(province_name: str) -> type:
    """
    Dynamically creates a SQLAlchemy model for {province_name}_population table.
    Uses Column() instead of mapped_column() — works correctly with type().
    """
    table_name = f"{province_name}_population"
    class_name = f"{province_name.capitalize()}Population"

    attrs = {
        # ── Table config ──────────────────────────────────────
        "__tablename__": table_name,
        "__table_args__": (
            Index(
                f"ix_{table_name}_geom",
                "geom",
                postgresql_using="gist",
            ),
            Index(f"ix_{table_name}_time",  "time"),
            Index(f"ix_{table_name}_value", "value"),
            Index(f"ix_{table_name}_lat_lon", "lat", "lon"),
        ),

        # ── Columns (use Column() not mapped_column() with type()) ──
        "id": Column(Integer, primary_key=True, autoincrement=True),

        "value": Column(
            Numeric(precision=18, scale=6),
            nullable=True,
            comment="Selected signal value: either rscp_mtn or rscp_mci",
        ),

        "lat": Column(Float, nullable=False),
        "lon": Column(Float, nullable=False),

        "geom": Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=False,
        ),

        "time": Column(DateTime(timezone=False), nullable=True),
    }

    model = type(class_name, (Base,), attrs)
    return model


# ── Register all provinces here ───────────────────────────────
# To add a new province: just add the name to this list
PROVINCE_NAMES = ["esfahan", "mashhad", "tehran"]

# Built once at import time: {"esfahan": EsfahanPopulation, ...}
PopulationModels: dict[str, type] = {
    name: make_population_model(name)
    for name in PROVINCE_NAMES
}


def get_population_model(province: str) -> type:
    model = PopulationModels.get(province)
    if model is None:
        raise KeyError(
            f"No population model for province '{province}'. "
            f"Available: {list(PopulationModels.keys())}"
        )
    return model