# app/repositories/poi_agg.py
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi_agg import PoiAgg
from app.schemas.poi_agg import PoiAggRecordResponse


class PoiAggRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(
        self,
        *,
        city: Optional[str] = None,
        hex_id: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> List[PoiAggRecordResponse]:
        stmt = select(
            PoiAgg.hex_id,
            func.min(PoiAgg.city).label("city"),
            func.min(PoiAgg.slug).label("slug"),
            func.max(PoiAgg.count).label("count"),
        )

        if city is not None:
            stmt = stmt.where(func.lower(PoiAgg.city) == city.lower())
        if hex_id is not None:
            stmt = stmt.where(PoiAgg.hex_id == hex_id)
        if slug is not None:
            stmt = stmt.where(PoiAgg.slug == slug)

        stmt = stmt.group_by(PoiAgg.hex_id).order_by(PoiAgg.hex_id)
        res = await self.db.execute(stmt)
        return [PoiAggRecordResponse(**row._asdict()) for row in res.all()]
