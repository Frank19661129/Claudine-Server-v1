"""
User domain entity.
Part of Domain layer - contains business logic and rules.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class User:
    """
    User domain entity representing a user in the system.
    This is a pure domain object with business rules.
    """

    id: UUID
    email: str
    full_name: str
    provider: str  # "google" or "microsoft"
    is_active: bool
    created_at: datetime
    updated_at: datetime
    hashed_password: Optional[str] = None

    @classmethod
    def create(
        cls,
        email: str,
        full_name: str,
        provider: str,
        hashed_password: Optional[str] = None,
    ) -> "User":
        """
        Factory method to create a new user.
        Enforces business rules at creation time.
        """
        # Validate email format
        if not email or "@" not in email:
            raise ValueError("Invalid email address")

        # Validate provider
        if provider not in ["google", "microsoft", "local"]:
            raise ValueError(f"Invalid provider: {provider}")

        # OAuth users should not have passwords
        if provider in ["google", "microsoft"] and hashed_password:
            raise ValueError("OAuth users cannot have passwords")

        # Local users must have passwords
        if provider == "local" and not hashed_password:
            raise ValueError("Local users must have a password")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            email=email.lower().strip(),
            full_name=full_name.strip(),
            provider=provider,
            is_active=True,
            created_at=now,
            updated_at=now,
            hashed_password=hashed_password,
        )

    def deactivate(self) -> None:
        """Deactivate user account."""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Activate user account."""
        self.is_active = True
        self.updated_at = datetime.utcnow()

    def update_profile(self, full_name: Optional[str] = None) -> None:
        """Update user profile information."""
        if full_name:
            self.full_name = full_name.strip()
        self.updated_at = datetime.utcnow()

    def is_oauth_user(self) -> bool:
        """Check if user uses OAuth authentication."""
        return self.provider in ["google", "microsoft"]

    def is_local_user(self) -> bool:
        """Check if user uses local authentication."""
        return self.provider == "local"
