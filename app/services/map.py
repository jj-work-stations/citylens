# app/services/map.py
import uuid
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models.user import User
from app.repositories.province import ProvinceRepository
from app.services.base import BaseService

MARTIN_BASE = "http://martin:3000"


class MapService(BaseService):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.province_repo = ProvinceRepository(db)

    async def get_tile(
        self,
        user: User,
        layer: str,
        z: int,
        x: int,
        y: int,
        province_id: Optional[uuid.UUID] = None,
        bbox: Optional[str] = None,
    ) -> bytes:
        effective_bbox = await self._resolve_bbox(user, province_id, bbox)
        return await self._fetch(layer, z, x, y, effective_bbox)

    async def province_map_info(
        self, user: User, province_id: uuid.UUID
    ) -> dict:
        if not user.has_province_access(province_id):
            raise PermissionDeniedError("No access to this province")

        p = await self.province_repo.get_by_id(province_id)
        if not p:
            raise NotFoundError("Province", province_id)

        return {
            "province_id": str(p.id),
            "name": p.name,
            "bbox": p.bbox,
            "center": {"lat": p.center_lat, "lon": p.center_lon},
        }

    async def _resolve_bbox(
        self,
        user: User,
        province_id: Optional[uuid.UUID],
        bbox: Optional[str],
    ) -> Optional[str]:
        if province_id:
            if not user.has_province_access(province_id):
                raise PermissionDeniedError("No access to this province")
            p = await self.province_repo.get_by_id(province_id)
            if not p:
                raise NotFoundError("Province", province_id)
            if not p.bbox:
                raise ValueError("Province has no bbox configured")
            return p.bbox

        if user.is_tenant_admin and not bbox:
            raise PermissionDeniedError("province_id or bbox required")

        return bbox

    async def _fetch(
        self, layer: str, z: int, x: int, y: int, bbox: Optional[str]
    ) -> bytes:
        url = f"{MARTIN_BASE}/{layer}/{z}/{x}/{y}"
        params = {"bbox": bbox} if bbox else {}

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.RequestError as exc:
                raise ExternalServiceError("martin", str(exc))

        if resp.status_code == 204 or not resp.content:
            return b""
        if not resp.is_success:
            raise ExternalServiceError("martin", f"HTTP {resp.status_code}")
        return resp.content