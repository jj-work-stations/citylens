# app/schemas/population.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.population import PROVINCE_NAMES


class PopulationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:    int
    value: Optional[float]
    lat:   float
    lon:   float
    time:  Optional[datetime]


class PopulationStatsResponse(BaseModel):
    total_records: int
    value_avg:     Optional[float]
    value_min:     Optional[float]
    value_max:     Optional[float]


class PaginatedPopulationResponse(BaseModel):
    items:    List[PopulationRecordResponse]
    total:    int
    offset:   int
    limit:    int
    province: str