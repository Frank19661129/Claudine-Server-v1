"""
Refresh token repository for database operations.
Part of Infrastructure layer.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.infrastructure.database.models import RefreshTokenModel


class RefreshTokenRepository:
    """Repository for refresh token CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: UUID, token: str, expires_at: datetime) -> RefreshTokenModel:
        """
        Create a new refresh token.

        Args:
            user_id: User ID
            token: The refresh token string
            expires_at: When the token expires

        Returns:
            Created RefreshTokenModel
        """
        db_token = RefreshTokenModel(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            revoked=False,
        )
        self.db.add(db_token)
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_by_token(self, token: str) -> Optional[RefreshTokenModel]:
        """
        Get refresh token by token string.

        Args:
            token: The refresh token string

        Returns:
            RefreshTokenModel if found, None otherwise
        """
        return self.db.query(RefreshTokenModel).filter(
            RefreshTokenModel.token == token
        ).first()

    def get_valid_token(self, token: str) -> Optional[RefreshTokenModel]:
        """
        Get a valid (not expired, not revoked) refresh token.

        Args:
            token: The refresh token string

        Returns:
            RefreshTokenModel if valid, None otherwise
        """
        return self.db.query(RefreshTokenModel).filter(
            RefreshTokenModel.token == token,
            RefreshTokenModel.revoked == False,
            RefreshTokenModel.expires_at > datetime.utcnow(),
        ).first()

    def revoke(self, token: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            token: The refresh token string

        Returns:
            True if revoked, False if not found
        """
        db_token = self.get_by_token(token)
        if db_token:
            db_token.revoked = True
            self.db.commit()
            return True
        return False

    def revoke_all_for_user(self, user_id: UUID) -> int:
        """
        Revoke all refresh tokens for a user (e.g., on password change or logout all).

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        result = self.db.query(RefreshTokenModel).filter(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked == False,
        ).update({"revoked": True})
        self.db.commit()
        return result

    def cleanup_expired(self) -> int:
        """
        Delete all expired tokens (housekeeping).

        Returns:
            Number of tokens deleted
        """
        result = self.db.query(RefreshTokenModel).filter(
            RefreshTokenModel.expires_at < datetime.utcnow(),
        ).delete()
        self.db.commit()
        return result
