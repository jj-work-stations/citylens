# app/repositories/tracking/location_history.py
from datetime import datetime
from typing import Optional

from geoalchemy2.functions import ST_MakeEnvelope, ST_SetSRID, ST_Within, ST_X, ST_Y
from sqlalchemy import Integer, and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracking.city            import City
from app.models.tracking.location_history import LocationHistory
from app.models.tracking.person          import Person


class LocationHistoryRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_filters(
        self,
        gender:         Optional[str]      = None,
        age_min:        Optional[int]      = None,
        age_max:        Optional[int]      = None,
        city_id:        Optional[int]      = None,
        timestamp_from: Optional[datetime] = None,
        timestamp_to:   Optional[datetime] = None,
        bbox:           Optional[str]      = None,
    ) -> list:
        filters = []

        if gender:
            filters.append(Person.gender == gender.upper())
        if age_min is not None:
            filters.append(Person.age >= age_min)
        if age_max is not None:
            filters.append(Person.age <= age_max)
        if city_id is not None:
            filters.append(Person.city_id == city_id)
        if timestamp_from:
            filters.append(LocationHistory.timestamp >= timestamp_from)
        if timestamp_to:
            filters.append(LocationHistory.timestamp <= timestamp_to)
        if bbox:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
            envelope = ST_SetSRID(ST_MakeEnvelope(xmin, ymin, xmax, ymax), 4326)
            filters.append(ST_Within(LocationHistory.location, envelope))

        return filters

    async def get_records(
        self,
        gender:         Optional[str]      = None,
        age_min:        Optional[int]      = None,
        age_max:        Optional[int]      = None,
        city_id:        Optional[int]      = None,
        timestamp_from: Optional[datetime] = None,
        timestamp_to:   Optional[datetime] = None,
        bbox:           Optional[str]      = None,
        page:           int                = 1,
        page_size:      int                = 100,
    ) -> tuple[list[dict], int]:
        filters = self._build_filters(
            gender, age_min, age_max, city_id,
            timestamp_from, timestamp_to, bbox,
        )

        base = (
            select(
                LocationHistory.id,
                LocationHistory.person_id,
                LocationHistory.timestamp,
                ST_X(LocationHistory.location).label("lon"),
                ST_Y(LocationHistory.location).label("lat"),
                Person.gender,
                Person.age,
                City.name.label("city_name"),
            )
            .join(Person, LocationHistory.person_id == Person.id)
            .join(City,   Person.city_id == City.id)
        )

        if filters:
            base = base.where(and_(*filters))

        # count
        count_q = select(func.count()).select_from(base.subquery())
        total   = (await self.db.execute(count_q)).scalar_one()

        # data
        data_q = (
            base
            .order_by(LocationHistory.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        rows = (await self.db.execute(data_q)).mappings().all()
        return [dict(r) for r in rows], total

    async def get_stats(
        self,
        gender:         Optional[str]      = None,
        age_min:        Optional[int]      = None,
        age_max:        Optional[int]      = None,
        city_id:        Optional[int]      = None,
        timestamp_from: Optional[datetime] = None,
        timestamp_to:   Optional[datetime] = None,
        bbox:           Optional[str]      = None,
    ) -> dict:
        filters = self._build_filters(
            gender, age_min, age_max, city_id,
            timestamp_from, timestamp_to, bbox,
        )

        q = (
            select(
                func.count(LocationHistory.id).label("total"),
                func.count(distinct(LocationHistory.person_id)).label("unique_people"),

                func.sum(
                    case((Person.gender == "M", 1), else_=0)
                ).label("gender_m"),

                func.sum(
                    case((Person.gender == "F", 1), else_=0)
                ).label("gender_f"),

                func.avg(Person.age).label("age_avg"),
                func.min(Person.age).label("age_min"),
                func.max(Person.age).label("age_max"),
            )
            .join(Person, LocationHistory.person_id == Person.id)
            .join(City,   Person.city_id == City.id)
        )

        if filters:
            q = q.where(and_(*filters))

        row = (await self.db.execute(q)).one()

        return {
            "total_records":  row.total        or 0,
            "unique_people":  row.unique_people or 0,
            "gender_m_count": int(row.gender_m  or 0),
            "gender_f_count": int(row.gender_f  or 0),
            "age_avg":        float(row.age_avg) if row.age_avg else None,
            "age_min":        row.age_min,
            "age_max":        row.age_max,
        }