# app/repositories/population.py
from datetime import datetime
from typing import Optional

from geoalchemy2.functions import ST_MakeEnvelope, ST_SetSRID, ST_Within
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.population import get_population_model


class PopulationRepository:
    """
    Single repository for any province population table.
    Just pass the province name.
    """

    def __init__(self, province: str, db: AsyncSession):
        self.db    = db
        self.model = get_population_model(province)

    def _filters(
        self,
        value_min: Optional[float]    = None,
        value_max: Optional[float]    = None,
        time_from: Optional[datetime] = None,
        time_to:   Optional[datetime] = None,
        bbox:      Optional[str]      = None,
    ) -> list:
        f = []

        if value_min is not None:
            f.append(self.model.value >= value_min)
        if value_max is not None:
            f.append(self.model.value <= value_max)
        if time_from is not None:
            f.append(self.model.time >= time_from)
        if time_to is not None:
            f.append(self.model.time <= time_to)
        if bbox:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
            envelope = ST_SetSRID(ST_MakeEnvelope(xmin, ymin, xmax, ymax), 4326)
            f.append(ST_Within(self.model.geom, envelope))

        return f

    async def get_records(
        self,
        value_min: Optional[float]    = None,
        value_max: Optional[float]    = None,
        time_from: Optional[datetime] = None,
        time_to:   Optional[datetime] = None,
        bbox:      Optional[str]      = None,
        limit:     int                = 1000,
        offset:    int                = 0,
    ) -> tuple[list, int]:
        filters = self._filters(value_min, value_max, time_from, time_to, bbox)

        count_q = select(func.count()).select_from(self.model)
        if filters:
            count_q = count_q.where(and_(*filters))
        total = (await self.db.execute(count_q)).scalar_one()

        data_q = select(self.model)
        if filters:
            data_q = data_q.where(and_(*filters))
        data_q = data_q.offset(offset).limit(limit)

        rows = (await self.db.execute(data_q)).scalars().all()
        return rows, total

    async def get_stats(
        self,
        time_from: Optional[datetime] = None,
        time_to:   Optional[datetime] = None,
        bbox:      Optional[str]      = None,
    ) -> dict:
        filters = self._filters(time_from=time_from, time_to=time_to, bbox=bbox)

        q = select(
            func.count().label("total"),
            func.avg(self.model.value).label("avg"),
            func.min(self.model.value).label("min"),
            func.max(self.model.value).label("max"),
        ).select_from(self.model)

        if filters:
            q = q.where(and_(*filters))

        row = (await self.db.execute(q)).one()

        return {
            "total_records": row.total,
            "value_avg":     float(row.avg) if row.avg else None,
            "value_min":     float(row.min) if row.min else None,
            "value_max":     float(row.max) if row.max else None,
        }

    async def bulk_insert(self, records: list[dict]) -> int:
        if not records:
            return 0
        await self.db.execute(self.model.__table__.insert(), records)
        await self.db.commit()
        return len(records)