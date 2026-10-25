# app/apis/v1/auth.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.core.exceptions import AppError
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    LogoutRequest,
    LogoutAllRequest,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def _svc(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


def _get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    ua = request.headers.get("user-agent")
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
    return ua, ip


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    svc: AuthService = Depends(_svc),
):
    try:
        ua, ip = _get_client_info(request)
        return await svc.login(payload.phone, payload.password, ua, ip)
    except AppError as e:
        raise e.to_http()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    svc: AuthService = Depends(_svc),
):
    try:
        ua, ip = _get_client_info(request)
        return await svc.refresh(payload.refresh_token, ua, ip)
    except AppError as e:
        raise e.to_http()


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    svc: AuthService = Depends(_svc),
):
    try:
        await svc.logout(payload.refresh_token)
    except AppError as e:
        raise e.to_http()


@router.post("/logout-all", status_code=204)
async def logout_all(
    current_user: CurrentUser,
    svc: AuthService = Depends(_svc),
):
    try:
        await svc.logout_all(current_user.id)
    except AppError as e:
        raise e.to_http()


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user