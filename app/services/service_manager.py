# app/services/service_manager.py
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models.user import User
from app.repositories.service import ServiceRepository
from app.services.base import BaseService


@dataclass
class ServiceResult:
    service_name: str
    success: bool
    data: Any
    status_code: int
    error: Optional[str] = None


class ServiceManager(BaseService):
    """
    Single entry-point for all calls to the 4 black-box services.
    Enforces access control: tenant_admins only reach assigned services.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.repo = ServiceRepository(db)

    def _check_access(self, user: User, service_id: uuid.UUID) -> None:
        if user.is_admin:
            return
        if not user.has_service_access(service_id):
            raise PermissionDeniedError(f"No access to service {service_id}")

    async def call(
        self,
        user: User,
        service_id: uuid.UUID,
        method: str,
        path: str,
        body: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> ServiceResult:
        service = await self.repo.get_by_id(service_id)
        if not service:
            raise NotFoundError("Service", service_id)

        self._check_access(user, service_id)

        base_url = settings.service_urls.get(service.service_type.value)
        if not base_url:
            raise ExternalServiceError(service.name, "No URL configured")

        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        async with httpx.AsyncClient(timeout=settings.SERVICE_TIMEOUT) as client:
            try:
                resp = await client.request(method.upper(), url, json=body, params=params)
            except httpx.RequestError as exc:
                raise ExternalServiceError(service.name, str(exc))

        return ServiceResult(
            service_name=service.name,
            success=resp.is_success,
            data=resp.json() if resp.content else None,
            status_code=resp.status_code,
            error=None if resp.is_success else resp.text,
        )

    async def list_accessible(self, user: User) -> list:
        if user.is_admin:
            services, _ = await self.repo.get_all(limit=100)
            return services
        return user.services