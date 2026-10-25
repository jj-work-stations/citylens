# app/services/auth.py
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_password,
)
from app.repositories.token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.base import BaseService


class AuthService(BaseService):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.user_repo = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    async def login(
        self,
        phone: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        user = await self.user_repo.get_by_phone(phone)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        if user.status != "active":
            raise InactiveAccountError()

        access_token, _ = create_access_token(str(user.id), user.role.value)
        raw_refresh, refresh_hash, refresh_expires = create_refresh_token()

        await self.token_repo.create(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,  # plain token sent ONCE to client
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def refresh(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        token_hash = hash_token(refresh_token)

        stored = await self.token_repo.get_by_hash(token_hash)
        if not stored:
            raise InvalidTokenError("Refresh token not found")
        if stored.revoked:
            # Token reuse detected — revoke ALL user tokens (security)
            await self.token_repo.revoke_all_for_user(stored.user_id)
            raise InvalidTokenError("Token reuse detected — all sessions revoked")
        if stored.expires_at < datetime.now(timezone.utc):
            raise InvalidTokenError("Refresh token expired")

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or user.status != "active":
            raise InvalidCredentialsError()

        # Rotate: revoke old, issue new
        await self.token_repo.revoke(stored.id)

        access_token, _ = create_access_token(str(user.id), user.role.value)
        new_raw, new_hash, new_expires = create_refresh_token()

        await self.token_repo.create(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=new_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return {
            "access_token": access_token,
            "refresh_token": new_raw,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout(
        self,
        refresh_token: str,
    ) -> None:
        """Revoke a specific refresh token"""
        token_hash = hash_token(refresh_token)
        stored = await self.token_repo.get_by_hash(token_hash)
        if stored:
            await self.token_repo.revoke(stored.id)

    async def logout_all(
        self,
        user_id: uuid.UUID,
    ) -> int:
        """Revoke ALL refresh tokens for a user (password change, security)"""
        return await self.token_repo.revoke_all_for_user(user_id)