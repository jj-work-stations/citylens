# app/services/poi_agg.py
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.repositories.poi_agg import PoiAggRepository


class PoiAggService:
    def __init__(self, db: AsyncSession):
        self.repo = PoiAggRepository(db)

    async def list_records(
        self,
        *,
        user,
        city: Optional[str] = None,
        hex_id: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> List:
        try:
            return await self.repo.list_all(
                city=city,
                hex_id=hex_id,
                slug=slug,
            )
        except Exception as exc:
            raise AppError.internal(
                "Failed to query POI aggregate data",
                details={
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
