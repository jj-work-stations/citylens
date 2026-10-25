# app/apis/v1/users.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.core.exceptions import AppError
from app.schemas.base import PaginatedResponse
from app.schemas.user import (
    AssignProvincesRequest,
    AssignServicesRequest,
    ChangePasswordRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _svc(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    _: AdminUser,
    svc: UserService = Depends(_svc),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    role: Optional[str] = Query(None, description="Filter by role: admin or tenant_admin"),
    province_id: Optional[uuid.UUID] = Query(None, description="Filter by province assignment"),
    service_id: Optional[uuid.UUID] = Query(None, description="Filter by service assignment"),
    search: Optional[str] = Query(None, description="Search phone, first_name, or last_name"),  # ← NEW
):
    users, total = await svc.list_users(
        skip=(page - 1) * page_size,
        limit=page_size,
        role=role,
        province_id=province_id,
        service_id=service_id,
        search=search,
    )
    return PaginatedResponse.build(users, total, page, page_size)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreateRequest,
    # _: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        return await svc.create_user(**payload.model_dump())
    except AppError as e:
        raise e.to_http()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        return await svc.get_user(user_id)
    except AppError as e:
        raise e.to_http()


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    _: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        return await svc.update_user(user_id, **payload.model_dump(exclude_none=True))
    except AppError as e:
        raise e.to_http()


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        await svc.delete_user(user_id, current_user.id)
    except AppError as e:
        raise e.to_http()


@router.put("/{user_id}/provinces", response_model=UserResponse)
async def assign_provinces(
    user_id: uuid.UUID,
    payload: AssignProvincesRequest,
    _: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        return await svc.assign_provinces(user_id, payload.province_ids)
    except AppError as e:
        raise e.to_http()


@router.put("/{user_id}/services", response_model=UserResponse)
async def assign_services(
    user_id: uuid.UUID,
    payload: AssignServicesRequest,
    _: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        return await svc.assign_services(user_id, payload.service_ids)
    except AppError as e:
        raise e.to_http()


@router.post("/me/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: AdminUser,
    svc: UserService = Depends(_svc),
):
    try:
        await svc.change_password(current_user.id, payload.old_password, payload.new_password)
    except AppError as e:
        raise e.to_http()