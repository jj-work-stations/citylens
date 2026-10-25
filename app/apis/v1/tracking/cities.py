# app/apis/v1/tracking/cities.py
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AdminUser, TenantAdminUser
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.tracking.city import (
    AddCitiesRequest,
    AssignCitiesRequest,
    CityResponse,
    RemoveCitiesRequest,
    UserCityAssignmentResponse,
)
from app.services.tracking.city import CityService

router = APIRouter(prefix="/tracking/cities", tags=["Tracking - Cities"])


def _svc(db: AsyncSession = Depends(get_db)) -> CityService:
    return CityService(db)


def _assignment_response(
    user_id: uuid.UUID,
    cities:  list,
) -> UserCityAssignmentResponse:
    return UserCityAssignmentResponse(
        user_id         = str(user_id),
        assigned_cities = cities,
        total           = len(cities),
    )


# ── Public: list cities ────────────────────────────────────────────────────────

@router.get("", response_model=list[CityResponse])
async def list_cities(
    current_user: TenantAdminUser,
    svc: CityService = Depends(_svc),
):
    """
    List cities.
    - **admin**: all cities.
    - **tenant_admin**: only their assigned cities.
    """
    try:
        if current_user.is_admin:
            return await svc.list_cities()
        # tenant_admin sees only their cities
        return await svc.get_user_cities(current_user.id)
    except AppError as e:
        raise e.to_http()


# ── Admin: manage city assignments ────────────────────────────────────────────

@router.get(
    "/assignments/{user_id}",
    response_model=UserCityAssignmentResponse,
)
async def get_user_city_assignments(
    user_id: uuid.UUID,
    _:       AdminUser,
    svc:     CityService = Depends(_svc),
):
    """
    **Admin only** — Get cities currently assigned to a tenant_admin.
    """
    try:
        cities = await svc.get_user_cities(user_id)
        return _assignment_response(user_id, cities)
    except AppError as e:
        raise e.to_http()


@router.put(
    "/assignments/{user_id}",
    response_model=UserCityAssignmentResponse,
)
async def assign_cities_to_user(
    user_id: uuid.UUID,
    body:    AssignCitiesRequest,
    _:       AdminUser,
    svc:     CityService = Depends(_svc),
):
    """
    **Admin only** — **Replace** all city assignments for a tenant_admin.

    Sends the complete desired set of city IDs.
    Any previously assigned city not in the list will be removed.
    """
    try:
        cities = await svc.assign_cities(user_id, body.city_ids)
        return _assignment_response(user_id, cities)
    except AppError as e:
        raise e.to_http()


@router.post(
    "/assignments/{user_id}/add",
    response_model=UserCityAssignmentResponse,
)
async def add_cities_to_user(
    user_id: uuid.UUID,
    body:    AddCitiesRequest,
    _:       AdminUser,
    svc:     CityService = Depends(_svc),
):
    """
    **Admin only** — **Add** cities to a tenant_admin without removing existing ones.
    """
    try:
        cities = await svc.add_cities(user_id, body.city_ids)
        return _assignment_response(user_id, cities)
    except AppError as e:
        raise e.to_http()


@router.post(
    "/assignments/{user_id}/remove",
    response_model=UserCityAssignmentResponse,
)
async def remove_cities_from_user(
    user_id: uuid.UUID,
    body:    RemoveCitiesRequest,
    _:       AdminUser,
    svc:     CityService = Depends(_svc),
):
    """
    **Admin only** — **Remove** specific cities from a tenant_admin.
    """
    try:
        cities = await svc.remove_cities(user_id, body.city_ids)
        return _assignment_response(user_id, cities)
    except AppError as e:
        raise e.to_http()