"""
User repository for database operations.
Part of Infrastructure layer.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.domain.entities.user import User
from app.infrastructure.database.models import UserModel


class UserRepository:
    """
    Repository for User entity database operations.
    Implements the repository pattern for User domain entities.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User) -> User:
        """
        Create a new user in the database.

        Args:
            user: User domain entity

        Returns:
            Created user domain entity

        Raises:
            ValueError: If user with email already exists
        """
        db_user = UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            provider=user.provider,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            return self._to_domain(db_user)
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"User with email {user.email} already exists")

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User's UUID

        Returns:
            User domain entity if found, None otherwise
        """
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_domain(db_user) if db_user else None

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User's email address

        Returns:
            User domain entity if found, None otherwise
        """
        db_user = (
            self.db.query(UserModel)
            .filter(UserModel.email == email.lower().strip())
            .first()
        )
        return self._to_domain(db_user) if db_user else None

    def update(self, user: User) -> User:
        """
        Update an existing user.

        Args:
            user: User domain entity with updates

        Returns:
            Updated user domain entity
        """
        db_user = self.db.query(UserModel).filter(UserModel.id == user.id).first()
        if not db_user:
            raise ValueError(f"User with ID {user.id} not found")

        db_user.email = user.email
        db_user.full_name = user.full_name
        db_user.is_active = user.is_active
        db_user.updated_at = user.updated_at

        self.db.commit()
        self.db.refresh(db_user)
        return self._to_domain(db_user)

    def delete(self, user_id: UUID) -> bool:
        """
        Delete a user (hard delete).

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return False

        self.db.delete(db_user)
        self.db.commit()
        return True

    def exists_by_email(self, email: str) -> bool:
        """
        Check if a user with the given email exists.

        Args:
            email: Email address to check

        Returns:
            True if user exists, False otherwise
        """
        return (
            self.db.query(UserModel)
            .filter(UserModel.email == email.lower().strip())
            .first()
            is not None
        )

    @staticmethod
    def _to_domain(db_user: UserModel) -> User:
        """
        Convert database model to domain entity.

        Args:
            db_user: UserModel database object

        Returns:
            User domain entity
        """
        return User(
            id=db_user.id,
            email=db_user.email,
            full_name=db_user.full_name,
            provider=db_user.provider,
            hashed_password=db_user.hashed_password,
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
        )
