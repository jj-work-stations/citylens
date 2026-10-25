# app/schemas/service.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.service import ServiceType


class ServiceCreateRequest(BaseModel):
    name: str
    service_type: ServiceType
    description: Optional[str] = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    service_type: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime