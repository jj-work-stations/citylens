# app/services/population.py
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.population import PROVINCE_NAMES
from app.models.user import User
from app.repositories.population import PopulationRepository


class PopulationService:

    def __init__(self, province: str, db: AsyncSession):
        if province not in PROVINCE_NAMES:
            raise NotFoundError("Province population", province)
        self.province = province
        self.repo     = PopulationRepository(province, db)

    def _check_access(self, user: User) -> None:
        if user.is_admin:
            return
        # check user has access to this province by name
        has_access = any(
            p.code.lower() == self.province.lower() or
            p.name.lower() == self.province.lower()
            for p in user.provinces
        )
        if not has_access:
            raise PermissionDeniedError(
                f"No access to {self.province} population data"
            )

    async def list_records(
        self,
        user:      User,
        value_min: Optional[float]    = None,
        value_max: Optional[float]    = None,
        time_from: Optional[datetime] = None,
        time_to:   Optional[datetime] = None,
        bbox:      Optional[str]      = None,
        limit:     int                = 1000,
        offset:    int                = 0,
    ) -> tuple[list, int]:
        self._check_access(user)
        return await self.repo.get_records(
            value_min=value_min,
            value_max=value_max,
            time_from=time_from,
            time_to=time_to,
            bbox=bbox,
            limit=limit,
            offset=offset,
        )

    async def get_stats(
        self,
        user:      User,
        time_from: Optional[datetime] = None,
        time_to:   Optional[datetime] = None,
        bbox:      Optional[str]      = None,
    ) -> dict:
        self._check_access(user)
        return await self.repo.get_stats(
            time_from=time_from,
            time_to=time_to,
            bbox=bbox,
        )