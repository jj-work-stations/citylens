# app/schemas/poi_agg.py
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PoiAggRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hex_id: str
    city: Optional[str] = None
    slug: Optional[str] = None
    count: Optional[int] = None
