# app/apis/v1/population.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantAdminUser
from app.core.exceptions import AppError
from app.models.population import PROVINCE_NAMES
from app.schemas.population import (
    PaginatedPopulationResponse,
    PopulationStatsResponse,
)
from app.services.population import PopulationService

router = APIRouter(prefix="/population", tags=["Population"])

VALID_PROVINCES = ", ".join(PROVINCE_NAMES)


def _svc(
    province: str = Path(description=f"Province name. One of: {VALID_PROVINCES}"),
    db: AsyncSession = Depends(get_db),
) -> PopulationService:
    if province not in PROVINCE_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Province '{province}' not found. Valid: {VALID_PROVINCES}",
        )
    return PopulationService(province, db)


@router.get("/{province}", response_model=PaginatedPopulationResponse)
async def list_records(
    current_user: TenantAdminUser,
    svc: PopulationService = Depends(_svc),
    value_min: Optional[float]    = Query(None, description="Min signal value"),
    value_max: Optional[float]    = Query(None, description="Max signal value"),
    time_from: Optional[datetime] = Query(None),
    time_to:   Optional[datetime] = Query(None),
    bbox:      Optional[str]      = Query(None, description="xmin,ymin,xmax,ymax"),
    limit:     int                = Query(1000, ge=1, le=10000),
    offset:    int                = Query(0, ge=0),
):
    try:
        rows, total = await svc.list_records(
            user=current_user,
            value_min=value_min,
            value_max=value_max,
            time_from=time_from,
            time_to=time_to,
            bbox=bbox,
            limit=limit,
            offset=offset,
        )
        return PaginatedPopulationResponse(
            items=rows,
            total=total,
            offset=offset,
            limit=limit,
            province=svc.province,
        )
    except AppError as e:
        raise e.to_http()


@router.get("/{province}/stats", response_model=PopulationStatsResponse)
async def get_stats(
    current_user: TenantAdminUser,
    svc: PopulationService = Depends(_svc),
    time_from: Optional[datetime] = Query(None),
    time_to:   Optional[datetime] = Query(None),
    bbox:      Optional[str]      = Query(None),
):
    try:
        return await svc.get_stats(
            user=current_user,
            time_from=time_from,
            time_to=time_to,
            bbox=bbox,
        )
    except AppError as e:
        raise e.to_http()