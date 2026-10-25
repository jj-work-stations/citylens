# app/services/province.py
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.province import Province
from app.repositories.province import ProvinceRepository
from app.services.base import BaseService


class ProvinceService(BaseService):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.repo = ProvinceRepository(db)

    async def get_province(self, province_id: uuid.UUID) -> Province:
        p = await self.repo.get_by_id(province_id)
        if not p:
            raise NotFoundError("Province", province_id)
        return p

    async def list_provinces(
        self, skip: int = 0, limit: int = 20
    ) -> tuple[list[Province], int]:
        return await self.repo.get_all(skip=skip, limit=limit)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Province]:
        return await self.repo.get_provinces_for_user(user_id)

    async def create_province(
        self,
        name: str,
        code: str,
        description: Optional[str] = None,
        center_lat: Optional[float] = None,
        center_lon: Optional[float] = None,
        bbox_xmin: Optional[float] = None,
        bbox_ymin: Optional[float] = None,
        bbox_xmax: Optional[float] = None,
        bbox_ymax: Optional[float] = None,
    ) -> Province:
        if await self.repo.get_by_code(code):
            raise ConflictError(f"Province code '{code}' already exists")

        return await self.repo.create(Province(
            name=name, code=code, description=description,
            center_lat=center_lat, center_lon=center_lon,
            bbox_xmin=bbox_xmin, bbox_ymin=bbox_ymin,
            bbox_xmax=bbox_xmax, bbox_ymax=bbox_ymax,
        ))

    async def update_province(
        self, province_id: uuid.UUID, **fields
    ) -> Province:
        province = await self.get_province(province_id)
        for k, v in fields.items():
            if v is not None:
                setattr(province, k, v)
        return await self.repo.update(province)

    async def delete_province(self, province_id: uuid.UUID) -> None:
        province = await self.get_province(province_id)
        await self.repo.delete(province)