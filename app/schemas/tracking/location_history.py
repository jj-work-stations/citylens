# app/schemas/tracking/location_history.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator, Field


class LocationHistoryFilter(BaseModel):
    """All filters for location history queries and tile generation."""

    # ── Person filters ─────────────────────────────────────────
    gender:  Optional[str]  = None   # "M" or "F"
    age_min: Optional[int]  = None
    age_max: Optional[int]  = None
    city_id: Optional[int]  = None

    # ── Time filters ───────────────────────────────────────────
    timestamp_from: Optional[datetime] = None
    timestamp_to:   Optional[datetime] = None

    # ── Spatial filter ─────────────────────────────────────────
    bbox: Optional[str] = None  # "xmin,ymin,xmax,ymax"
    allowed_city_ids: Optional[List[int]] = Field(None, exclude=True)


    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v and v.upper() not in ("M", "F"):
            raise ValueError("gender must be 'M' or 'F'")
        return v.upper() if v else v

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        if v:
            parts = v.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be 'xmin,ymin,xmax,ymax'")
            [float(p) for p in parts]
        return v


class LocationHistoryRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    person_id: int
    timestamp: datetime
    lat:       float
    lon:       float
    gender:    str
    age:       int
    city_name: str


class PaginatedLocationHistory(BaseModel):
    items:    list[LocationHistoryRecord]
    total:    int
    page:     int
    page_size: int


class LocationStatsResponse(BaseModel):
    total_records:  int
    unique_people:  int
    gender_m_count: int
    gender_f_count: int
    age_avg:        Optional[float]
    age_min:        Optional[int]
    age_max:        Optional[int]