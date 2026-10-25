# app/schemas/user.py
import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.user import UserRole, UserStatus
from app.schemas.tracking.city import CityResponse

# ── Validators ─────────────────────────────────────────────────

def _normalize_phone(v: str) -> str:
    v = v.strip().replace(" ", "").replace("-", "")
    if not re.match(r"^(\+98|0098|0)?9\d{9}$", v):
        raise ValueError("Invalid Iranian phone number")
    if v.startswith("+98"):
        v = "0" + v[3:]
    elif v.startswith("0098"):
        v = "0" + v[4:]
    return v


def _validate_national_code(v: str) -> str:
    v = v.strip()
    if not re.match(r"^\d{10}$", v):
        raise ValueError("National code must be exactly 10 digits")
    return v


# ── Requests ───────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    phone: str
    first_name: str
    last_name: str
    password: str
    role: UserRole = UserRole.TENANT_ADMIN
    national_code: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _normalize_phone(v)

    @field_validator("national_code")
    @classmethod
    def nc_valid(cls, v): return _validate_national_code(v) if v else v

    @field_validator("password")
    @classmethod
    def pw_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Cannot be empty")
        return v


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_code: Optional[str] = None
    status: Optional[UserStatus] = None
    is_verified:Optional[bool] = None

    @field_validator("national_code")
    @classmethod
    def nc_valid(cls, v): return _validate_national_code(v) if v else v


class AssignProvincesRequest(BaseModel):
    province_ids: List[UUID]


class AssignServicesRequest(BaseModel):
    service_ids: List[UUID]


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def pw_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# ── Responses ──────────────────────────────────────────────────

class ProvinceBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str


class ServiceBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    service_type: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    first_name: str
    last_name: str
    national_code: Optional[str]
    role: UserRole
    status: UserStatus
    is_verified: bool
    provinces: List[ProvinceBasic] = []
    services: List[ServiceBasic] = []
    cities:    List[CityResponse] = [] 
    created_at: datetime
    updated_at: datetime