# app/core/security.py
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

from jose import JWTError, jwt
import bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_token(token: str) -> str:
    """SHA-256 hash for storing refresh tokens"""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject: str, role: str) -> Tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, settings.ALGORITHM), expire


def create_refresh_token() -> Tuple[str, str, datetime]:
    """
    Returns: (raw_token, token_hash, expires_at)
    Raw token sent to client, hash stored in DB.
    """
    raw = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
    token_hash = hash_token(raw)
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return raw, token_hash, expire


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")