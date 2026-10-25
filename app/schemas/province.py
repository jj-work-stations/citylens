# app/schemas/province.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProvinceCreateRequest(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    bbox_xmin: Optional[float] = None
    bbox_ymin: Optional[float] = None
    bbox_xmax: Optional[float] = None
    bbox_ymax: Optional[float] = None


class ProvinceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    bbox_xmin: Optional[float] = None
    bbox_ymin: Optional[float] = None
    bbox_xmax: Optional[float] = None
    bbox_ymax: Optional[float] = None
    is_active: Optional[bool] = None


class ProvinceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: Optional[str]
    center_lat: Optional[float]
    center_lon: Optional[float]
    bbox: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime