# app/apis/v1/map.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantAdminUser
from app.core.exceptions import AppError
from app.services.map import MapService

router = APIRouter(prefix="/map", tags=["Map"])


def _svc(db: AsyncSession = Depends(get_db)) -> MapService:
    return MapService(db)


@router.get("/tiles/{layer}/{z}/{x}/{y}")
async def get_tile(
    layer: str,
    z: int,
    x: int,
    y: int,
    current_user: TenantAdminUser,
    svc: MapService = Depends(_svc),
    province_id: Optional[uuid.UUID] = Query(None),
    bbox: Optional[str] = Query(None),
):
    try:
        content = await svc.get_tile(
            user=current_user,
            layer=layer,
            z=z, x=x, y=y,
            province_id=province_id,
            bbox=bbox,
        )
    except AppError as e:
        raise e.to_http()

    if not content:
        return Response(status_code=204)

    return Response(
        content=content,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "max-age=3600"},
    )


@router.get("/province-info/{province_id}")
async def province_map_info(
    province_id: uuid.UUID,
    current_user: TenantAdminUser,
    svc: MapService = Depends(_svc),
):
    try:
        return await svc.province_map_info(current_user, province_id)
    except AppError as e:
        raise e.to_http()