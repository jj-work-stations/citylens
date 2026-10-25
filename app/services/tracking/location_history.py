# # app/services/tracking/location_history.py
# from datetime import datetime
# from typing import Optional

# from sqlalchemy.ext.asyncio import AsyncSession

# from app.repositories.tracking.location_history import LocationHistoryRepository
# from app.schemas.tracking.location_history import (
#     LocationHistoryFilter,
#     LocationStatsResponse,
#     PaginatedLocationHistory,
#     LocationHistoryRecord,
# )


# class LocationHistoryService:

#     def __init__(self, db: AsyncSession):
#         self.repo = LocationHistoryRepository(db)

#     async def list_records(
#         self,
#         filters:   LocationHistoryFilter,
#         page:      int = 1,
#         page_size: int = 100,
#     ) -> PaginatedLocationHistory:
#         rows, total = await self.repo.get_records(
#             gender         = filters.gender,
#             age_min        = filters.age_min,
#             age_max        = filters.age_max,
#             city_id        = filters.city_id,
#             timestamp_from = filters.timestamp_from,
#             timestamp_to   = filters.timestamp_to,
#             bbox           = filters.bbox,
#             page           = page,
#             page_size      = page_size,
#         )

#         items = [LocationHistoryRecord(**row) for row in rows]

#         return PaginatedLocationHistory(
#             items     = items,
#             total     = total,
#             page      = page,
#             page_size = page_size,
#         )

#     async def get_stats(
#         self, filters: LocationHistoryFilter
#     ) -> LocationStatsResponse:
#         stats = await self.repo.get_stats(
#             gender         = filters.gender,
#             age_min        = filters.age_min,
#             age_max        = filters.age_max,
#             city_id        = filters.city_id,
#             timestamp_from = filters.timestamp_from,
#             timestamp_to   = filters.timestamp_to,
#             bbox           = filters.bbox,
#         )
#         return LocationStatsResponse(**stats)












# app/services/tracking/location_history.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.tracking.location_history import LocationHistoryRepository
from app.schemas.tracking.location_history import (
    LocationHistoryFilter,
    LocationHistoryRecord,
    LocationStatsResponse,
    PaginatedLocationHistory,
)


class LocationHistoryService:

    def __init__(self, db: AsyncSession):
        self.repo = LocationHistoryRepository(db)

    async def list_records(
        self,
        filters:   LocationHistoryFilter,
        page:      int = 1,
        page_size: int = 100,
    ) -> PaginatedLocationHistory:

        rows, total = await self.repo.get_records(
            gender           = filters.gender,
            age_min          = filters.age_min,
            age_max          = filters.age_max,
            city_id          = filters.city_id,
            timestamp_from   = filters.timestamp_from,
            timestamp_to     = filters.timestamp_to,
            bbox             = filters.bbox,
            allowed_city_ids = filters.allowed_city_ids,  # ← security scope
            page             = page,
            page_size        = page_size,
        )

        return PaginatedLocationHistory(
            items     = [LocationHistoryRecord(**row) for row in rows],
            total     = total,
            page      = page,
            page_size = page_size,
        )

    async def get_stats(
        self,
        filters: LocationHistoryFilter,
    ) -> LocationStatsResponse:

        stats = await self.repo.get_stats(
            gender           = filters.gender,
            age_min          = filters.age_min,
            age_max          = filters.age_max,
            city_id          = filters.city_id,
            timestamp_from   = filters.timestamp_from,
            timestamp_to     = filters.timestamp_to,
            bbox             = filters.bbox,
            allowed_city_ids = filters.allowed_city_ids,  # ← security scope
        )

        return LocationStatsResponse(**stats)