# app/apis/v1/services.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AdminUser, TenantAdminUser
from app.core.exceptions import AppError
from app.schemas.service import ServiceCreateRequest, ServiceResponse
from app.services.service_manager import ServiceManager
from app.repositories.service import ServiceRepository
from app.models.service import Service

router = APIRouter(prefix="/services", tags=["Services"])


def _svc(db: AsyncSession = Depends(get_db)) -> ServiceManager:
    return ServiceManager(db)


class CallRequest(BaseModel):
    method: str = "GET"
    path: str
    body: Optional[dict] = None
    params: Optional[dict] = None


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    current_user: TenantAdminUser,
    manager: ServiceManager = Depends(_svc),
):
    return await manager.list_accessible(current_user)


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    payload: ServiceCreateRequest,
    _: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    repo = ServiceRepository(db)
    service = Service(**payload.model_dump())
    return await repo.create(service)


@router.post("/{service_id}/call")
async def call_service(
    service_id: uuid.UUID,
    payload: CallRequest,
    current_user: TenantAdminUser,
    manager: ServiceManager = Depends(_svc),
):
    try:
        return await manager.call(
            user=current_user,
            service_id=service_id,
            method=payload.method,
            path=payload.path,
            body=payload.body,
            params=payload.params,
        )
    except AppError as e:
        raise e.to_http()