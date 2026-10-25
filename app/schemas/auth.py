# app/schemas/auth.py
from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def normalize(cls, v: str) -> str:
        v = v.strip().replace(" ", "").replace("-", "")
        if v.startswith("+98"):
            v = "0" + v[3:]
        elif v.startswith("0098"):
            v = "0" + v[4:]
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class LogoutAllRequest(BaseModel):
    pass  # uses current user


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int