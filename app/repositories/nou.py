
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nou import ForecastHexHourly

_QUERY_CANCELED_SQLSTATE = "57014"


def _is_statement_timeout(exc: DBAPIError) -> bool:
    """Detect PostgreSQL statement_timeout cancellations."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    sqlstate = (
        getattr(orig, "sqlstate", None)
        or getattr(orig, "pgcode", None)
    )
    if sqlstate == _QUERY_CANCELED_SQLSTATE:
        return True

    message = str(orig).lower()
    return (
        "canceling statement" in message
        or "statement timeout" in message
    )


class NouRepository:
    """Read-only queries against the external forecast database."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def build_filters(
        *,
        provinces: Optional[list[str]] = None,
        hex_id: Optional[str] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        count_min: Optional[float] = None,
        count_max: Optional[float] = None,
    ) -> list:
        filters = []

        if provinces is not None:
            if not provinces:
                # An explicitly empty access list must never mean
                # unrestricted access.
                filters.append(ForecastHexHourly.hex_id.is_(None))
            else:
                filters.append(
                    ForecastHexHourly.province.in_(provinces)
                )

        if hex_id is not None:
            filters.append(ForecastHexHourly.hex_id == hex_id)

        if time_from is not None:
            filters.append(
                ForecastHexHourly.target_time >= time_from
            )

        if time_to is not None:
            filters.append(
                ForecastHexHourly.target_time <= time_to
            )

        if count_min is not None:
            filters.append(
                ForecastHexHourly.predicted_user_count >= count_min
            )

        if count_max is not None:
            filters.append(
                ForecastHexHourly.predicted_user_count <= count_max
            )

        return filters

    async def count_distinct_hexes(self, filters: list) -> int:
        """Count distinct hex IDs matching all active filters."""
        statement = select(
            func.count(func.distinct(ForecastHexHourly.hex_id))
        )

        if filters:
            statement = statement.where(*filters)

        result = await self.db.execute(statement)
        return int(result.scalar_one())

    async def get_hex_page(
        self,
        filters: list,
        *,
        limit: int,
        offset: int,
    ) -> list[str]:
        """Return a stable, ordered page of distinct hex IDs."""
        statement = (
            select(ForecastHexHourly.hex_id)
            .where(*filters)
            .distinct()
            .order_by(ForecastHexHourly.hex_id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def get_records_for_hexes(
        self,
        hex_ids: Sequence[str],
        filters: list,
    ) -> list[dict]:
        """
        Fetch response columns only.

        This avoids creating ORM instances and populating the session
        identity map for every forecast row.
        """
        if not hex_ids:
            return []

        statement = (
            select(
                ForecastHexHourly.hex_id.label("hex_id"),
                ForecastHexHourly.province.label("province"),
                ForecastHexHourly.target_time.label("target_time"),
                ForecastHexHourly.predicted_user_count.label(
                    "predicted_user_count"
                ),
            )
            .where(
                ForecastHexHourly.hex_id.in_(hex_ids),
                *filters,
            )
            .order_by(
                ForecastHexHourly.province,
                ForecastHexHourly.hex_id,
                ForecastHexHourly.target_time,
            )
        )

        result = await self.db.execute(statement)
        return [dict(row) for row in result.mappings().all()]
