# app/repositories/tracking/city.py
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracking.city import City
from app.models.user import User, tenant_admin_city


class CityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> list[City]:
        result = await self.db.execute(select(City).order_by(City.name))
        return result.scalars().all()

    async def get_by_id(self, city_id: int) -> City | None:
        result = await self.db.execute(select(City).where(City.id == city_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, city_ids: list[int]) -> list[City]:
        result = await self.db.execute(
            select(City).where(City.id.in_(city_ids)).order_by(City.name)
        )
        return result.scalars().all()

    async def get_user_cities(self, user_id) -> list[City]:
        result = await self.db.execute(
            select(City)
            .join(
                tenant_admin_city,
                City.id == tenant_admin_city.c.city_id,
            )
            .where(tenant_admin_city.c.user_id == user_id)
            .order_by(City.name)
        )
        return result.scalars().all()

    async def assign_cities(self, user_id, city_ids: list[int]) -> list[City]:
        """Replace ALL city assignments for a user."""
        try:
            # 1. Delete existing
            await self.db.execute(
                delete(tenant_admin_city).where(
                    tenant_admin_city.c.user_id == user_id
                )
            )

            # 2. Insert new
            if city_ids:
                await self.db.execute(
                    insert(tenant_admin_city),
                    [{"user_id": user_id, "city_id": cid} for cid in city_ids],
                )

            # 3. Commit
            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        return await self.get_user_cities(user_id)

    async def add_cities(self, user_id, city_ids: list[int]) -> list[City]:
        """Add cities without removing existing ones."""
        try:
            # Get current to avoid PK violations
            existing     = await self.get_user_cities(user_id)
            existing_ids = {c.id for c in existing}
            new_ids      = [cid for cid in city_ids if cid not in existing_ids]

            if new_ids:
                await self.db.execute(
                    insert(tenant_admin_city),
                    [{"user_id": user_id, "city_id": cid} for cid in new_ids],
                )
                await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        return await self.get_user_cities(user_id)

    async def remove_cities(self, user_id, city_ids: list[int]) -> list[City]:
        """Remove specific cities from a user."""
        try:
            await self.db.execute(
                delete(tenant_admin_city).where(
                    tenant_admin_city.c.user_id == user_id,
                    tenant_admin_city.c.city_id.in_(city_ids),
                )
            )
            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

        return await self.get_user_cities(user_id)