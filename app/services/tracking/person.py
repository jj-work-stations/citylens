# app/services/tracking/person.py
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.tracking.person import Person
from app.repositories.tracking.person import PersonRepository


class PersonService:

    def __init__(self, db: AsyncSession):
        self.repo = PersonRepository(db)

    async def get_person(self, person_id: int) -> Person:
        person = await self.repo.get_by_id(person_id)
        if not person:
            raise NotFoundError("Person", person_id)
        return person

    async def list_people(
        self,
        gender:    Optional[str] = None,
        age_min:   Optional[int] = None,
        age_max:   Optional[int] = None,
        city_id:   Optional[int] = None,
        page:      int = 1,
        page_size: int = 50,
    ) -> tuple[list[Person], int]:
        return await self.repo.get_all(
            gender   = gender,
            age_min  = age_min,
            age_max  = age_max,
            city_id  = city_id,
            page     = page,
            page_size= page_size,
        )

    async def get_stats_by_city(self) -> list[dict]:
        return await self.repo.get_stats_by_city()