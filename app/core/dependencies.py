# app/core/dependencies.py
import uuid
from typing import Annotated, Optional, List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    # inline import to avoid circular
    from app.repositories.user import UserRepository

    user = await UserRepository(db).get_by_id(uuid.UUID(payload["sub"]))

    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")

    request.state.current_user = user
    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user


async def get_current_tenant_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role not in (UserRole.ADMIN, UserRole.TENANT_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    return current_user

# ── Type aliases used across routers ──────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_admin)]
TenantAdminUser = Annotated[User, Depends(get_current_tenant_admin)]
DBSession = Annotated[AsyncSession, Depends(get_db)]

def get_allowed_city_ids(
    current_user: TenantAdminUser,
) -> Optional[List[int]]:
    """
    Returns None  → admin, no restriction.
    Returns [...]  → tenant_admin, restricted to assigned cities.
    """
    return current_user.allowed_city_ids


AllowedCityIds = Annotated[Optional[List[int]], Depends(get_allowed_city_ids)]

