# app/services/audit.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository
from app.services.base import BaseService


class AuditService(BaseService):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.repo = AuditRepository(db)

    async def get_logs(
        self,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        status_code: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list, int]:
        return await self.repo.get_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            status_code=status_code,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
