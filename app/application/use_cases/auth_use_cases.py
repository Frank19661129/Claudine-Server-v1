"""
Authentication use cases.
Part of Application layer - orchestrates business logic.
"""
from typing import Optional
from app.domain.entities.user import User
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.services.password import hash_password, verify_password
from app.infrastructure.services.jwt import create_access_token


class RegisterUserUseCase:
    """
    Use case for registering a new user.
    Handles local user registration with email/password.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

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

        # Generate JWT token
        access_token = create_access_token(
            user_id=created_user.id,
            email=created_user.email,
            provider=created_user.provider,
        )

        return {
            "user": {
                "id": str(created_user.id),
                "email": created_user.email,
                "full_name": created_user.full_name,
                "provider": created_user.provider,
                "is_active": created_user.is_active,
            },
            "access_token": access_token,
            "token_type": "bearer",
        }


class LoginUserUseCase:
    """
    Use case for user login with email/password.
    Validates credentials and returns JWT token.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

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

        # Generate JWT token
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            provider=user.provider,
        )

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "provider": user.provider,
                "is_active": user.is_active,
            },
            "access_token": access_token,
            "token_type": "bearer",
        }


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
        from uuid import UUID

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
            "created_at": user.created_at.isoformat(),
        }
