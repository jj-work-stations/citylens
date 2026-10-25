
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ExternalServiceError,
    PermissionDeniedError,
    QueryTooExpensiveError,
)
from app.models.user import User
from app.repositories.nou import NouRepository, _is_statement_timeout

logger = logging.getLogger(__name__)


class NouService:
    """Business logic for querying forecast data with tenant access control."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = NouRepository(db)

    @staticmethod
    def _allowed_provinces(user: User) -> Optional[list[str]]:
        """Return None for admins, otherwise the user's allowed names/codes."""
        if user.is_admin:
            return None

        allowed = []
        for province in user.provinces:
            if province.name:
                allowed.append(province.name)
            if province.code:
                allowed.append(province.code)

        # De-duplicate case-insensitively while preserving original values.
        unique = {}
        for value in allowed:
            unique.setdefault(value.casefold(), value)

        if not unique:
            raise PermissionDeniedError(
                "No province access assigned to this account"
            )

        return list(unique.values())

    @classmethod
    def _province_filter(
        cls,
        user: User,
        requested: Optional[str],
    ) -> Optional[list[str]]:
        allowed = cls._allowed_provinces(user)

        if allowed is None:
            return [requested] if requested else None

        allowed_by_key = {
            value.casefold(): value for value in allowed
        }

        if requested:
            canonical = allowed_by_key.get(requested.casefold())
            if canonical is None:
                raise PermissionDeniedError(
                    f"No access to '{requested}' forecast data"
                )
            return [canonical]

        return allowed

    @staticmethod
    def _validate_ranges(
        *,
        time_from: Optional[datetime],
        time_to: Optional[datetime],
        count_min: Optional[float],
        count_max: Optional[float],
    ) -> None:
        if (
            time_from is not None
            and time_to is not None
            and time_from > time_to
        ):
            raise ValueError("target_time_from must be <= target_time_to")

        if (
            count_min is not None
            and count_max is not None
            and count_min > count_max
        ):
            raise ValueError(
                "predicted_user_count_min must be <= "
                "predicted_user_count_max"
            )

    @staticmethod
    def _handle_db_error(exc: SQLAlchemyError) -> None:
        if isinstance(exc, DBAPIError) and _is_statement_timeout(exc):
            raise QueryTooExpensiveError(
                "Query exceeded the forecast database time limit. "
                "Narrow the time range, specify a province or hex_id, "
                "or reduce the page size."
            ) from exc

        logger.exception("Forecast database query failed")
        raise ExternalServiceError(
            "forecast database",
            exc.__class__.__name__,
        ) from exc

    async def list_records(
        self,
        user: User,
        province: Optional[str] = None,
        hex_id: Optional[str] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        count_min: Optional[float] = None,
        count_max: Optional[float] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Return (forecast_rows, total_distinct_hexes).

        Pagination applies to distinct hex IDs, not response rows.
        """
        self._validate_ranges(
            time_from=time_from,
            time_to=time_to,
            count_min=count_min,
            count_max=count_max,
        )

        provinces = self._province_filter(user, province)

        filters = self.repo.build_filters(
            provinces=provinces,
            hex_id=hex_id,
            time_from=time_from,
            time_to=time_to,
            count_min=count_min,
            count_max=count_max,
        )

        try:
            total = await self.repo.count_distinct_hexes(filters)
            if total == 0 or offset >= total:
                return [], total

            if hex_id is not None:
                # The count above correctly returns 0 or 1, taking
                # every other filter into account.
                hex_ids = [hex_id]
            else:
                hex_ids = await self.repo.get_hex_page(
                    filters,
                    limit=limit,
                    offset=offset,
                )

            rows = await self.repo.get_records_for_hexes(
                hex_ids,
                filters,
            )
            return rows, total

        except SQLAlchemyError as exc:
            self._handle_db_error(exc)
            raise  # Keeps static type checkers satisfied.
