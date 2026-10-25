# app/apis/v1/provinces.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import AdminUser, TenantAdminUser
from app.core.exceptions import AppError, PermissionDeniedError
from app.schemas.base import PaginatedResponse
from app.schemas.province import (
    ProvinceCreateRequest,
    ProvinceResponse,
    ProvinceUpdateRequest,
)
from app.services.province import ProvinceService

router = APIRouter(prefix="/provinces", tags=["Provinces"])


def _svc(db: AsyncSession = Depends(get_db)) -> ProvinceService:
    return ProvinceService(db)


@router.get("", response_model=PaginatedResponse[ProvinceResponse])
async def list_provinces(
    current_user: TenantAdminUser,
    svc: ProvinceService = Depends(_svc),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
):
    skip = (page - 1) * page_size
    if current_user.is_admin:
        provinces, total = await svc.list_provinces(skip=skip, limit=page_size)
    else:
        provinces = await svc.list_for_user(current_user.id)
        total = len(provinces)
        provinces = provinces[skip: skip + page_size]

    return PaginatedResponse.build(provinces, total, page, page_size)


@router.post("", response_model=ProvinceResponse, status_code=201)
async def create_province(
    payload: ProvinceCreateRequest,
    _: AdminUser,
    svc: ProvinceService = Depends(_svc),
):
    try:
        return await svc.create_province(**payload.model_dump())
    except AppError as e:
        raise e.to_http()


@router.get("/{province_id}", response_model=ProvinceResponse)
async def get_province(
    province_id: uuid.UUID,
    current_user: TenantAdminUser,
    svc: ProvinceService = Depends(_svc),
):
    try:
        if not current_user.has_province_access(province_id):
            raise PermissionDeniedError("No access to this province")
        return await svc.get_province(province_id)
    except AppError as e:
        raise e.to_http()


@router.patch("/{province_id}", response_model=ProvinceResponse)
async def update_province(
    province_id: uuid.UUID,
    payload: ProvinceUpdateRequest,
    _: AdminUser,
    svc: ProvinceService = Depends(_svc),
):
    try:
        return await svc.update_province(
            province_id, **payload.model_dump(exclude_none=True)
        )
    except AppError as e:
        raise e.to_http()


@router.delete("/{province_id}", status_code=204)
async def delete_province(
    province_id: uuid.UUID,
    _: AdminUser,
    svc: ProvinceService = Depends(_svc),
):
    try:
        await svc.delete_province(province_id)
    except AppError as e:
        raise e.to_http()