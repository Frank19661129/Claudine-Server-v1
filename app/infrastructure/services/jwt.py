"""
JWT token service for authentication.
Part of Infrastructure layer.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID
import secrets
from jose import JWTError, jwt
from app.core.config import settings


def create_access_token(user_id: UUID, email: str, provider: str) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: User's UUID
        email: User's email address
        provider: Authentication provider (google, microsoft, local)

    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "email": email,
        "provider": provider,
        "iat": datetime.utcnow(),  # Issued at
        "exp": expire,  # Expiration
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def extract_user_id_from_token(token: str) -> Optional[UUID]:
    """
    Extract user ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        User UUID if valid, None otherwise
    """
    payload = decode_access_token(token)
    if payload is None:
        return None

    try:
        return UUID(payload.get("sub"))
    except (ValueError, TypeError):
        return None


def create_refresh_token() -> Tuple[str, datetime]:
    """
    Create a secure refresh token.

    Returns:
        Tuple of (token_string, expires_at_datetime)
    """
    token = secrets.token_urlsafe(64)  # 64 bytes = 512 bits of entropy
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


def create_token_pair(user_id: UUID, email: str, provider: str) -> dict:
    """
    Create both access token and refresh token for a user.

    Args:
        user_id: User's UUID
        email: User's email address
        provider: Authentication provider

    Returns:
        Dict with access_token, refresh_token, and expires_at
    """
    access_token = create_access_token(user_id, email, provider)
    refresh_token, refresh_expires_at = create_refresh_token()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_token_expires_at": refresh_expires_at,
    }
