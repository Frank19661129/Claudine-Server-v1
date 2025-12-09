"""
Authentication use cases.
Part of Application layer - orchestrates business logic.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.entities.user import User
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.services.password import hash_password, verify_password
from app.infrastructure.services.jwt import create_access_token, create_token_pair


class RegisterUserUseCase:
    """
    Use case for registering a new user.
    Handles local user registration with email/password.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, email: str, password: str, full_name: str) -> dict:
        """
        Register a new local user.

        Args:
            email: User's email address
            password: Plain text password
            full_name: User's full name

        Returns:
            Dict with user info and access token

        Raises:
            ValueError: If user already exists or validation fails
        """
        # Check if user already exists
        if self.user_repository.exists_by_email(email):
            raise ValueError("User with this email already exists")

        # Validate password strength
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        # Hash password
        hashed_password = hash_password(password)

        # Create user domain entity
        user = User.create(
            email=email,
            full_name=full_name,
            provider="local",
            hashed_password=hashed_password,
        )

        # Save to database
        created_user = self.user_repository.create(user)

        # Generate token pair (access + refresh)
        tokens = create_token_pair(
            user_id=created_user.id,
            email=created_user.email,
            provider=created_user.provider,
        )

        # Store refresh token in database
        refresh_repo = RefreshTokenRepository(self.db)
        refresh_repo.create(
            user_id=created_user.id,
            token=tokens["refresh_token"],
            expires_at=tokens["refresh_token_expires_at"],
        )

        return {
            "user": {
                "id": str(created_user.id),
                "email": created_user.email,
                "full_name": created_user.full_name,
                "provider": created_user.provider,
                "is_active": created_user.is_active,
            },
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
        }


class LoginUserUseCase:
    """
    Use case for user login with email/password.
    Validates credentials and returns JWT token.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, email: str, password: str) -> dict:
        """
        Authenticate user with email and password.

        Args:
            email: User's email address
            password: Plain text password

        Returns:
            Dict with user info and access token

        Raises:
            ValueError: If credentials are invalid
        """
        # Get user from database
        user = self.user_repository.get_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")

        # Check if user is local (not OAuth)
        if not user.is_local_user():
            raise ValueError(f"This account uses {user.provider} authentication")

        # Check if account is active
        if not user.is_active:
            raise ValueError("Account is disabled")

        # Verify password
        if not user.hashed_password:
            raise ValueError("Invalid account configuration")

        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        # Generate token pair (access + refresh)
        tokens = create_token_pair(
            user_id=user.id,
            email=user.email,
            provider=user.provider,
        )

        # Store refresh token in database
        refresh_repo = RefreshTokenRepository(self.db)
        refresh_repo.create(
            user_id=user.id,
            token=tokens["refresh_token"],
            expires_at=tokens["refresh_token_expires_at"],
        )

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "provider": user.provider,
                "is_active": user.is_active,
                "photo_url": user.photo_url,
            },
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
        }


class RefreshTokenUseCase:
    """
    Use case for refreshing an access token using a refresh token.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, refresh_token: str) -> dict:
        """
        Refresh access token using a valid refresh token.

        Args:
            refresh_token: The refresh token string

        Returns:
            Dict with new access_token and refresh_token

        Raises:
            ValueError: If refresh token is invalid or expired
        """
        refresh_repo = RefreshTokenRepository(self.db)

        # Get and validate refresh token
        db_token = refresh_repo.get_valid_token(refresh_token)
        if not db_token:
            raise ValueError("Invalid or expired refresh token")

        # Get user
        user = self.user_repository.get_by_id(db_token.user_id)
        if not user:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("Account is disabled")

        # Revoke old refresh token (rotation for security)
        refresh_repo.revoke(refresh_token)

        # Generate new token pair
        tokens = create_token_pair(
            user_id=user.id,
            email=user.email,
            provider=user.provider,
        )

        # Store new refresh token
        refresh_repo.create(
            user_id=user.id,
            token=tokens["refresh_token"],
            expires_at=tokens["refresh_token_expires_at"],
        )

        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
        }


class LogoutUseCase:
    """
    Use case for logging out (revoking refresh token).
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(self, refresh_token: str) -> bool:
        """
        Logout by revoking the refresh token.

        Args:
            refresh_token: The refresh token to revoke

        Returns:
            True if revoked, False if token not found
        """
        refresh_repo = RefreshTokenRepository(self.db)
        return refresh_repo.revoke(refresh_token)


class GetCurrentUserUseCase:
    """
    Use case for getting current authenticated user.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(self, user_id: str) -> Optional[dict]:
        """
        Get current user by ID.

        Args:
            user_id: User's UUID as string

        Returns:
            User info dict if found, None otherwise
        """
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            return None

        user = self.user_repository.get_by_id(user_uuid)
        if not user:
            return None

        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "provider": user.provider,
            "is_active": user.is_active,
            "photo_url": user.photo_url,
            "created_at": user.created_at.isoformat(),
        }
