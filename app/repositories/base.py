# app/repositories/base.py  (unchanged — same as before, just path corrected)
from typing import Generic, List, Optional, Tuple, Type, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    def __init__(self, model: Type[M], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: UUID) -> Optional[M]:
        r = await self.db.execute(select(self.model).where(self.model.id == id))
        return r.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 20) -> Tuple[List[M], int]:
        total = (
            await self.db.execute(select(func.count()).select_from(self.model))
        ).scalar_one()
        rows = (
            await self.db.execute(select(self.model).offset(skip).limit(limit))
        ).scalars().all()
        return rows, total

    async def create(self, obj: M) -> M:
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: M) -> M:
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: M) -> None:
        await self.db.delete(obj)
        await self.db.commit()