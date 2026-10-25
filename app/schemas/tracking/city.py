# app/schemas/tracking/city.py
from pydantic import BaseModel, ConfigDict, Field


class CityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:   int
    name: str


# ── Assignment request/response ────────────────────────────────────────────────

class AssignCitiesRequest(BaseModel):
    """Replace ALL city assignments for a tenant_admin."""
    city_ids: list[int] = Field(
        ...,
        description="Full list of city IDs to assign. Replaces current assignments.",
        examples=[[1, 2, 3]],
    )


class AddCitiesRequest(BaseModel):
    """Add cities without removing existing ones."""
    city_ids: list[int] = Field(
        ...,
        description="City IDs to add to existing assignments.",
        examples=[[4, 5]],
    )


class RemoveCitiesRequest(BaseModel):
    """Remove specific cities from a tenant_admin."""
    city_ids: list[int] = Field(
        ...,
        description="City IDs to remove.",
        examples=[[2]],
    )


class UserCityAssignmentResponse(BaseModel):
    """Returned after any assignment operation."""
    user_id:       str
    assigned_cities: list[CityResponse]
    total:           int