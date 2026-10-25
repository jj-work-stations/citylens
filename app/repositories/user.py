# app/repositories/user.py
import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, UserStatus, tenant_admin_province, tenant_admin_service
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    def _base_options(self):
        """Always load provinces, services, and cities together."""
        return [
            selectinload(User.provinces),
            selectinload(User.services),
            selectinload(User.cities),   # ← NEW
        ]

    async def get_by_id(self, id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .where(User.id == id)
            .options(*self._base_options())
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .where(User.phone == phone)
            .options(*self._base_options())
        )
        return result.scalar_one_or_none()

    async def get_by_national_code(self, national_code: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.national_code == national_code)
        )
        return result.scalar_one_or_none()

    async def phone_exists(self, phone: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
        q = select(User).where(User.phone == phone)
        if exclude_id:
            q = q.where(User.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        role: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[User], int]:
        filters = []
        if role:
            filters.append(User.role == role)
        if search:
            term = f"%{search}%"
            filters.append(
                or_(
                    User.phone.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                )
            )

        count_q = select(func.count()).select_from(User)
        if filters:
            count_q = count_q.where(and_(*filters))
        total = (await self.db.execute(count_q)).scalar_one()

        q = select(User).options(*self._base_options())
        if filters:
            q = q.where(and_(*filters))
        q = q.offset(skip).limit(limit)

        result = await self.db.execute(q)
        return result.scalars().all(), total

    async def get_tenant_admins(
        self,
        province_id: Optional[uuid.UUID] = None,
        service_id:  Optional[uuid.UUID] = None,
        skip:        int = 0,
        limit:       int = 20,
        search:      Optional[str] = None,
    ) -> Tuple[List[User], int]:
        q = (
            select(User)
            .where(User.role == UserRole.TENANT_ADMIN)
            .options(*self._base_options())
        )

        if province_id:
            q = q.join(
                tenant_admin_province,
                and_(
                    tenant_admin_province.c.user_id == User.id,
                    tenant_admin_province.c.province_id == province_id,
                ),
            )
        if service_id:
            q = q.join(
                tenant_admin_service,
                and_(
                    tenant_admin_service.c.user_id == User.id,
                    tenant_admin_service.c.service_id == service_id,
                ),
            )
        if search:
            term = f"%{search}%"
            q = q.where(
                or_(
                    User.phone.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                )
            )

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        result = await self.db.execute(q.offset(skip).limit(limit))
        return result.scalars().all(), total