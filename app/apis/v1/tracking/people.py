# app/apis/v1/tracking/people.py
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantAdminUser
from app.core.exceptions import AppError
from app.schemas.tracking.person import PersonResponse
from app.schemas.base import PaginatedResponse
from app.services.tracking.person import PersonService

router = APIRouter(prefix="/tracking/people", tags=["Tracking - People"])


def _svc(db: AsyncSession = Depends(get_db)) -> PersonService:
    return PersonService(db)


@router.get("", response_model=PaginatedResponse[PersonResponse])
async def list_people(
    current_user: TenantAdminUser,
    svc:      PersonService  = Depends(_svc),
    gender:   Optional[str] = Query(None, description="M or F"),
    age_min:  Optional[int] = Query(None, ge=0,  le=120),
    age_max:  Optional[int] = Query(None, ge=0,  le=120),
    city_id:  Optional[int] = Query(None),
    page:     int           = Query(1,  ge=1),
    page_size: int          = Query(50, ge=1, le=500),
):
    try:
        people, total = await svc.list_people(
            gender    = gender,
            age_min   = age_min,
            age_max   = age_max,
            city_id   = city_id,
            page      = page,
            page_size = page_size,
        )
        return PaginatedResponse.build(people, total, page, page_size)
    except AppError as e:
        raise e.to_http()


@router.get("/stats/by-city")
async def stats_by_city(
    current_user: TenantAdminUser,
    svc: PersonService = Depends(_svc),
):
    """
    People count, gender split and age stats grouped by city.

    Response example:
    [
      {
        "city_id": 1,
        "city_name": "Tehran",
        "total": 3334,
        "male_count": 1634,
        "female_count": 1700,
        "avg_age": 42.3,
        "min_age": 18,
        "max_age": 100
      }
    ]
    """
    return await svc.get_stats_by_city()


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(
    person_id: int,
    current_user: TenantAdminUser,
    svc: PersonService = Depends(_svc),
):
    try:
        return await svc.get_person(person_id)
    except AppError as e:
        raise e.to_http()