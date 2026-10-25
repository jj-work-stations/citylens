# app/repositories/poi_agg.py
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi_agg import PoiAgg


class PoiAggRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(
        self,
        *,
        city: Optional[str] = None,
        hex_id: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> List[PoiAgg]:
        # poi_agg is already aggregated upstream; just fetch the rows.
        # No DISTINCT / GROUP BY here — those masked nothing and only
        # distorted the data (see note below about duplicate causes).
        stmt = select(PoiAgg)

        if city is not None:
            stmt = stmt.where(func.lower(PoiAgg.city) == city.lower())
        if hex_id is not None:
            stmt = stmt.where(PoiAgg.hex_id == hex_id)
        if slug is not None:
            stmt = stmt.where(PoiAgg.slug == slug)

        stmt = stmt.order_by(PoiAgg.hex_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
