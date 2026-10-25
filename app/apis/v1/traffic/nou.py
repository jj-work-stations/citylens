
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TenantAdminUser
from app.core.exceptions import AppError
from app.core.forecast_database import get_forecast_db
from app.schemas.nou import PaginatedNouForecastResponse
from app.services.nou import NouService

router = APIRouter(prefix="/traffic/nou", tags=["Traffic - Nou"])


def _svc(db: AsyncSession = Depends(get_forecast_db)) -> NouService:
    return NouService(db)


@router.get("/forecast", response_model=PaginatedNouForecastResponse)
async def list_forecast(
    current_user: TenantAdminUser,
    svc: NouService = Depends(_svc),
    province: Optional[str] = Query(
        None, description="Province name or code"
    ),
    hex_id: Optional[str] = Query(None, description="H3 hex ID"),
    target_time_from: Optional[datetime] = Query(
        None, description="Inclusive start time (ISO 8601)"
    ),
    target_time_to: Optional[datetime] = Query(
        None, description="Inclusive end time (ISO 8601)"
    ),
    predicted_user_count_min: Optional[float] = Query(None, ge=0),
    predicted_user_count_max: Optional[float] = Query(None, ge=0),
    limit: int = Query(
        1000, ge=1, le=5000,
        description="Maximum distinct hex IDs per page",
    ),
    offset: int = Query(
        0, ge=0, description="Offset among distinct hex IDs"
    ),
) -> PaginatedNouForecastResponse:
    if (
        target_time_from is not None
        and target_time_to is not None
        and target_time_from > target_time_to
    ):
        raise HTTPException(
            status_code=422,
            detail="target_time_from must be <= target_time_to",
        )

    if (
        predicted_user_count_min is not None
        and predicted_user_count_max is not None
        and predicted_user_count_min > predicted_user_count_max
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "predicted_user_count_min must be <= "
                "predicted_user_count_max"
            ),
        )

    try:
        items, total = await svc.list_records(
            user=current_user,
            province=province,
            hex_id=hex_id,
            time_from=target_time_from,
            time_to=target_time_to,
            count_min=predicted_user_count_min,
            count_max=predicted_user_count_max,
            limit=limit,
            offset=offset,
        )

        return PaginatedNouForecastResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
        )
    except AppError as exc:
        raise exc.to_http() from exc
