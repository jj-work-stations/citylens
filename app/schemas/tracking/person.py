# app/schemas/tracking/person.py
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.tracking.city import CityResponse


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:     int
    gender: str
    age:    int
    city:   CityResponse