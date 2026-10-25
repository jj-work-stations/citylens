# services/api/repositories/province.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.province import Province
from app.repositories.base import BaseRepository


class ProvinceRepository(BaseRepository[Province]):
    def __init__(self, db: AsyncSession):
        super().__init__(Province, db)

    async def get_by_code(self, code: str) -> Optional[Province]:
        result = await self.db.execute(
            select(Province).where(Province.code == code)
        )
        return result.scalar_one_or_none()

    async def get_active_provinces(self) -> List[Province]:
        result = await self.db.execute(
            select(Province)
            .where(Province.is_active == True)  # noqa: E712
            .options(selectinload(Province.tenant_admins))
        )
        return result.scalars().all()

    async def get_provinces_for_user(self, user_id: UUID) -> List[Province]:
        from app.models.user import tenant_admin_province
        result = await self.db.execute(
            select(Province)
            .join(
                tenant_admin_province,
                tenant_admin_province.c.province_id == Province.id,
            )
            .where(tenant_admin_province.c.user_id == user_id)
        )
        return result.scalars().all()