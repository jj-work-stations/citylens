# app/services/user.py
import uuid
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.province import ProvinceRepository
from app.repositories.service import ServiceRepository
from app.repositories.user import UserRepository
from app.services.base import BaseService


class UserService(BaseService):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.user_repo = UserRepository(db)
        self.province_repo = ProvinceRepository(db)
        self.service_repo = ServiceRepository(db)

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        role: Optional[str] = None,
        province_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,  # ← NEW
    ) -> Tuple[list[User], int]:
        if role == "tenant_admin" or province_id or service_id:
            return await self.user_repo.get_tenant_admins(
                province_id=province_id,
                service_id=service_id,
                skip=skip,
                limit=limit,
                search=search,
            )
        return await self.user_repo.get_all(
            skip=skip,
            limit=limit,
            role=role,
            search=search,
        )

    async def create_user(
        self,
        phone: str,
        first_name: str,
        last_name: str,
        password: str,
        role: UserRole,
        national_code: Optional[str] = None,
    ) -> User:
        if await self.user_repo.phone_exists(phone):
            raise ConflictError("Phone number already registered")

        if national_code and await self.user_repo.get_by_national_code(national_code):
            raise ConflictError("National code already registered")

        user = User(
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            national_code=national_code,
            hashed_password=hash_password(password),
            role=role,
        )
        return await self.user_repo.create(user)

    async def update_user(self, user_id: uuid.UUID, **fields) -> User:
        user = await self.get_user(user_id)
        for k, v in fields.items():
            if v is not None:
                setattr(user, k, v)
        return await self.user_repo.update(user)

    async def delete_user(
        self, user_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> None:
        if user_id == requesting_user_id:
            raise PermissionDeniedError("Cannot delete yourself")
        user = await self.get_user(user_id)
        await self.user_repo.delete(user)

    async def assign_provinces(
        self, user_id: uuid.UUID, province_ids: list[uuid.UUID]
    ) -> User:
        user = await self.get_user(user_id)
        if user.role != UserRole.TENANT_ADMIN:
            raise PermissionDeniedError("Only tenant_admin can be assigned provinces")

        provinces = []
        for pid in province_ids:
            p = await self.province_repo.get_by_id(pid)
            if not p:
                raise NotFoundError("Province", pid)
            provinces.append(p)

        user.provinces = provinces
        return await self.user_repo.update(user)

    async def assign_services(
        self, user_id: uuid.UUID, service_ids: list[uuid.UUID]
    ) -> User:
        user = await self.get_user(user_id)
        if user.role != UserRole.TENANT_ADMIN:
            raise PermissionDeniedError("Only tenant_admin can be assigned services")

        services = []
        for sid in service_ids:
            s = await self.service_repo.get_by_id(sid)
            if not s:
                raise NotFoundError("Service", sid)
            services.append(s)

        user.services = services
        return await self.user_repo.update(user)

    async def change_password(
        self, user_id: uuid.UUID, old_password: str, new_password: str
    ) -> None:
        user = await self.get_user(user_id)
        if not verify_password(old_password, user.hashed_password):
            raise InvalidCredentialsError()
        user.hashed_password = hash_password(new_password)
        await self.user_repo.update(user)