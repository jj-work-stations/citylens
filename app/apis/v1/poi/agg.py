# app/apis/v1/poi/agg.py
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TenantAdminUser
from app.core.exceptions import AppError
from app.core.forecast_database import get_forecast_db
from app.schemas.poi_agg import PoiAggRecordResponse
from app.services.poi_agg import PoiAggService

router = APIRouter(prefix="/poi", tags=["POI"])


def _svc(db: AsyncSession = Depends(get_forecast_db)) -> PoiAggService:
    return PoiAggService(db)


@router.get("/agg", response_model=List[PoiAggRecordResponse])
async def list_poi_agg(
    current_user: TenantAdminUser,
    svc: PoiAggService = Depends(_svc),
    city: Optional[str] = Query(None, description="City name (case-insensitive)"),
    hex_id: Optional[str] = Query(None, description="H3 hex id"),
    slug: Optional[str] = Query(None, description="POI slug"),
):
    try:
        return await svc.list_records(
            user=current_user,
            city=city,
            hex_id=hex_id,
            slug=slug,
        )
    except AppError as e:
        raise e.to_http()
