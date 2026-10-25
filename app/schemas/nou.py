
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NouForecastRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hex_id: str
    province: Optional[str] = None
    target_time: Optional[datetime] = None
    predicted_user_count: Optional[float] = None


class PaginatedNouForecastResponse(BaseModel):
    """Forecast records for a page of distinct hex IDs."""

    items: list[NouForecastRecordResponse]
    total: int  # Total distinct matching hex IDs
    offset: int
    limit: int
