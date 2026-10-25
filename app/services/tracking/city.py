# app/services/tracking/city.py
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.models.tracking.city import City
from app.models.user import UserRole
from app.repositories.tracking.city import CityRepository
from app.repositories.user import UserRepository


class CityService:

    def __init__(self, db: AsyncSession):
        self.repo      = CityRepository(db)
        self.user_repo = UserRepository(db)

    # ── Basic queries ──────────────────────────────────────────────────────────

    async def list_cities(self) -> list[City]:
        return await self.repo.get_all()

    async def get_city(self, city_id: int) -> City:
        city = await self.repo.get_by_id(city_id)
        if not city:
            raise NotFoundError("City", city_id)
        return city

    # ── Assignment helpers ─────────────────────────────────────────────────────

    async def _validate_user_and_cities(
        self,
        user_id:  uuid.UUID,
        city_ids: list[int],
    ) -> None:
        """
        Validate:
        - User exists and is a tenant_admin
        - All requested city_ids exist in the DB
        Raises AppError / NotFoundError on failure.
        """
        user = await self.user_repo.get_by_id(str(user_id))
        if not user:
            raise NotFoundError("User", str(user_id))
        if user.role != UserRole.TENANT_ADMIN:
            raise AppError(
                status_code=400,
                detail="Cities can only be assigned to tenant_admin users.",
            )

        if city_ids:
            found = await self.repo.get_by_ids(city_ids)
            found_ids = {c.id for c in found}
            missing = set(city_ids) - found_ids
            if missing:
                raise AppError(
                    status_code=422,
                    detail=f"City IDs not found: {sorted(missing)}",
                )

    async def get_user_cities(self, user_id: uuid.UUID) -> list[City]:
        user = await self.user_repo.get_by_id(str(user_id))
        if not user:
            raise NotFoundError("User", str(user_id))
        return await self.repo.get_user_cities(user_id)

    async def assign_cities(
        self,
        user_id:  uuid.UUID,
        city_ids: list[int],
    ) -> list[City]:
        """Replace all city assignments."""
        await self._validate_user_and_cities(user_id, city_ids)
        return await self.repo.assign_cities(user_id, city_ids)

    async def add_cities(
        self,
        user_id:  uuid.UUID,
        city_ids: list[int],
    ) -> list[City]:
        """Add cities (keeps existing)."""
        await self._validate_user_and_cities(user_id, city_ids)
        return await self.repo.add_cities(user_id, city_ids)

    async def remove_cities(
        self,
        user_id:  uuid.UUID,
        city_ids: list[int],
    ) -> list[City]:
        """Remove specific cities."""
        await self._validate_user_and_cities(user_id, city_ids)
        return await self.repo.remove_cities(user_id, city_ids)