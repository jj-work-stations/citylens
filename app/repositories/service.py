# services/api/repositories/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    def __init__(self, db: AsyncSession):
        super().__init__(Service, db)