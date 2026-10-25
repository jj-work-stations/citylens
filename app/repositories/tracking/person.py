# app/repositories/tracking/person.py
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from typing import Optional

from app.models.tracking.city   import City
from app.models.tracking.person import Person


class PersonRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, person_id: int) -> Optional[Person]:
        result = await self.db.execute(
            select(Person)
            .options(joinedload(Person.city))
            .where(Person.id == person_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        gender:    Optional[str] = None,
        age_min:   Optional[int] = None,
        age_max:   Optional[int] = None,
        city_id:   Optional[int] = None,
        page:      int = 1,
        page_size: int = 50,
    ) -> tuple[list[Person], int]:
        from sqlalchemy import and_

        filters = self._build_filters(gender, age_min, age_max, city_id)

        count_q = select(func.count()).select_from(Person)
        if filters:
            count_q = count_q.where(and_(*filters))
        total = (await self.db.execute(count_q)).scalar_one()

        data_q = select(Person).options(joinedload(Person.city))
        if filters:
            data_q = data_q.where(and_(*filters))
        data_q = data_q.offset((page - 1) * page_size).limit(page_size)

        rows = (await self.db.execute(data_q)).scalars().all()
        return rows, total

    async def get_by_city(self, city_id: int) -> list[Person]:
        result = await self.db.execute(
            select(Person)
            .options(joinedload(Person.city))
            .where(Person.city_id == city_id)
        )
        return result.scalars().all()

    async def get_stats_by_city(self) -> list[dict]:
        result = await self.db.execute(
            select(
                City.id.label("city_id"),
                City.name.label("city_name"),
                func.count(Person.id).label("total"),

                func.sum(
                    case((Person.gender == "M", 1), else_=0)
                ).label("male_count"),

                func.sum(
                    case((Person.gender == "F", 1), else_=0)
                ).label("female_count"),

                func.avg(Person.age).label("avg_age"),
                func.min(Person.age).label("min_age"),
                func.max(Person.age).label("max_age"),
            )
            .join(City, Person.city_id == City.id)
            .group_by(City.id, City.name)
            .order_by(City.name)
        )
        return [dict(row._mapping) for row in result.all()]

    def _build_filters(
        self,
        gender:  Optional[str] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        city_id: Optional[int] = None,
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
        return filters