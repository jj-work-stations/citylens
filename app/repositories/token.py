# app/repositories/token.py
import uuid
from datetime import datetime, timezone  # ← add timezone here
from typing import Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(
        self,
        token_id: uuid.UUID,
        replaced_by: uuid.UUID | None = None,
    ) -> bool:
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(
                revoked=True,
                revoked_at=datetime.now(timezone.utc),  # ← now works
                replaced_by=replaced_by,
            )
        )
        await self.db.commit()
        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked == False,  # noqa: E712
                )
            )
            .values(
                revoked=True,
                revoked_at=datetime.now(timezone.utc),  # ← now works
            )
        )
        await self.db.commit()
        return result.rowcount

    async def cleanup_expired(self) -> int:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.expires_at < datetime.now(timezone.utc)  # ← now works
            )
        )
        tokens = result.scalars().all()
        for t in tokens:
            await self.db.delete(t)
        await self.db.commit()
        return len(tokens)