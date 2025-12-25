"""
Onboarding use cases.
Part of Application layer - orchestrates onboarding flow.
"""
import os
import secrets
import string
import re
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.database.models import UserModel
from app.infrastructure.services.email_service import get_email_service


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_inbox_token() -> str:
    """Generate a 6-character alphanumeric token for inbox address."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(6))


def sanitize_email_prefix(email: str) -> str:
    """
    Extract and sanitize the local part of an email for use as inbox prefix.

    Examples:
        frank@madano.nl -> frank
        jan.de.vries@gmail.com -> jan-de-vries
        o'brien@test.com -> obrien
    """
    local_part = email.split('@')[0].lower()
    # Replace dots with hyphens
    local_part = local_part.replace('.', '-')
    # Remove any character that's not alphanumeric or hyphen
    local_part = re.sub(r'[^a-z0-9-]', '', local_part)
    # Remove consecutive hyphens
    local_part = re.sub(r'-+', '-', local_part)
    # Remove leading/trailing hyphens
    local_part = local_part.strip('-')
    return local_part


class StartEmailVerificationUseCase:
    """
    Use case for starting email verification.
    Generates a code and "sends" verification email.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID) -> dict:
        """
        Start email verification process.

        Args:
            user_id: User's UUID

        Returns:
            Dict with success status and message
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        if db_user.email_verified:
            return {"success": True, "message": "Email already verified"}

        # Generate verification code
        code = generate_verification_code()
        expires = datetime.utcnow() + timedelta(minutes=15)

        # Update user with verification code
        db_user.email_verification_code = code
        db_user.email_verification_expires = expires
        self.db.commit()

        # Send email via SendGrid
        email_service = get_email_service()
        email_result = email_service.send_email_verification_code(
            to_email=db_user.email,
            code=code
        )

        result = {
            "success": True,
            "message": f"Verification code sent to {db_user.email}",
        }

        # Include code in dev mode for testing (when email is faked)
        if email_result.get("fake"):
            result["_dev_code"] = code

        return result


class VerifyEmailUseCase:
    """
    Use case for verifying email with code.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID, code: str) -> dict:
        """
        Verify email with the provided code.

        Args:
            user_id: User's UUID
            code: 6-digit verification code

        Returns:
            Dict with success status
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        if db_user.email_verified:
            return {"success": True, "message": "Email already verified"}

        if not db_user.email_verification_code:
            raise ValueError("No verification code found. Please request a new one.")

        if datetime.utcnow() > db_user.email_verification_expires:
            raise ValueError("Verification code expired. Please request a new one.")

        if db_user.email_verification_code != code:
            raise ValueError("Invalid verification code")

        # Mark email as verified and clear code
        db_user.email_verified = True
        db_user.email_verification_code = None
        db_user.email_verification_expires = None
        self.db.commit()

        return {"success": True, "message": "Email verified successfully"}


class SuggestInboxAddressUseCase:
    """
    Use case for suggesting a unique inbox address.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID) -> dict:
        """
        Generate a unique inbox address suggestion.

        Args:
            user_id: User's UUID

        Returns:
            Dict with suggested inbox address
        """
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        base = sanitize_email_prefix(db_user.email)

        # Try to find a unique combination
        for _ in range(10):  # Max 10 attempts
            token = generate_inbox_token()
            local_part = f"{base}-{token}"

            # Check if unique
            existing = self.db.query(UserModel).filter(
                UserModel.inbox_prefix == local_part
            ).first()

            if not existing:
                return {
                    "success": True,
                    "suggested_address": f"{local_part}@inbox.pai-ai.com",
                    "local_part": local_part
                }

        # Fallback: extremely unlikely to reach here
        raise ValueError("Could not generate unique address. Please try again.")


class GenerateInboxAddressUseCase:
    """
    Use case for generating the PAI inbox address.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID, custom_prefix: Optional[str] = None) -> dict:
        """
        Generate inbox address for user.

        Args:
            user_id: User's UUID
            custom_prefix: The full local part of the inbox address (e.g., 'frank-abc123')

        Returns:
            Dict with inbox address info
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        # Use provided prefix or generate from email + token
        if custom_prefix:
            local_part = sanitize_email_prefix(custom_prefix)
        else:
            # Fallback: generate from email + random token
            base = sanitize_email_prefix(db_user.email)
            token = generate_inbox_token()
            local_part = f"{base}-{token}"

        # Validate length (max 64 chars for local part of email)
        if len(local_part) > 64:
            return {
                "success": False,
                "prefix_too_long": True,
                "suggested_prefix": local_part[:64],
                "current_length": len(local_part),
                "max_length": 64,
                "message": "Address is too long. Please shorten it."
            }

        # Check uniqueness
        existing = self.db.query(UserModel).filter(
            UserModel.inbox_prefix == local_part,
            UserModel.id != user_id
        ).first()
        if existing:
            return {
                "success": False,
                "message": "Dit adres is al in gebruik. Pas het aan."
            }

        # Update user - store the full local part in inbox_prefix, no separate token needed
        db_user.inbox_prefix = local_part
        db_user.inbox_token = "x"  # Placeholder for backwards compatibility
        self.db.commit()

        inbox_email = f"{local_part}@inbox.pai-ai.com"

        return {
            "success": True,
            "inbox_email": inbox_email,
            "message": f"Your PAI inbox is ready: {inbox_email}"
        }


class SendInboxVerificationUseCase:
    """
    Use case for sending inbox verification email.
    Sends an email FROM the user's PAI inbox TO their personal email.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID) -> dict:
        """
        Send inbox verification email.

        Args:
            user_id: User's UUID

        Returns:
            Dict with success status
        """
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        if not db_user.inbox_prefix:
            raise ValueError("Inbox not yet created")

        if db_user.inbox_verified:
            return {"success": True, "message": "Inbox already verified"}

        # Generate verification token (longer than 6-digit code for URL safety)
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)

        db_user.inbox_verification_token = token
        db_user.inbox_verification_expires = expires
        self.db.commit()

        inbox_email = db_user.inbox_email
        # Use production URL - can be overridden by env var later
        base_url = os.getenv("FRONTEND_URL", "http://localhost:5174")
        verification_url = f"{base_url}/verify-inbox?token={token}"

        # Send email via SendGrid FROM inbox_email TO db_user.email
        email_service = get_email_service()
        email_result = email_service.send_inbox_verification_email(
            pai_inbox=inbox_email,
            user_email=db_user.email,
            verification_url=verification_url
        )

        result = {
            "success": True,
            "message": f"Verificatie email verzonden naar {db_user.email}",
        }

        # Include URL in dev mode for testing (when email is faked)
        if email_result.get("fake"):
            result["_dev_verification_url"] = verification_url

        return result


class VerifyInboxUseCase:
    """
    Use case for verifying inbox via token from email link.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, token: str) -> dict:
        """
        Verify inbox with the provided token.

        Args:
            token: Verification token from email link

        Returns:
            Dict with success status
        """
        db_user = self.db.query(UserModel).filter(
            UserModel.inbox_verification_token == token
        ).first()

        if not db_user:
            raise ValueError("Invalid verification link")

        if db_user.inbox_verified:
            return {"success": True, "message": "Inbox already verified"}

        if datetime.utcnow() > db_user.inbox_verification_expires:
            raise ValueError("Verification link expired. Please request a new one.")

        # Mark inbox as verified and clear token
        db_user.inbox_verified = True
        db_user.inbox_verification_token = None
        db_user.inbox_verification_expires = None
        self.db.commit()

        return {"success": True, "message": "Inbox verified successfully"}


class StartPhoneVerificationUseCase:
    """
    Use case for starting phone verification.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID, phone_number: str) -> dict:
        """
        Start phone verification process.

        Args:
            user_id: User's UUID
            phone_number: Phone number to verify

        Returns:
            Dict with success status
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        # Normalize phone number (basic cleanup)
        phone = re.sub(r'[^0-9+]', '', phone_number)
        if not phone.startswith('+'):
            # Assume Dutch number if no country code
            if phone.startswith('0'):
                phone = '+31' + phone[1:]
            else:
                phone = '+31' + phone

        # Generate verification code
        code = generate_verification_code()
        expires = datetime.utcnow() + timedelta(minutes=15)

        # Update user
        db_user.phone_number = phone
        db_user.phone_verification_code = code
        db_user.phone_verification_expires = expires
        self.db.commit()

        # TODO: Actually send SMS via Twilio or similar
        print(f"[FAKE SMS] Verification code to {phone}: {code}")

        return {
            "success": True,
            "phone_number": phone,
            "message": f"Verification code sent to {phone}",
            "_dev_code": code
        }


class VerifyPhoneUseCase:
    """
    Use case for verifying phone with code.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID, code: str) -> dict:
        """
        Verify phone with the provided code.

        Args:
            user_id: User's UUID
            code: 6-digit verification code

        Returns:
            Dict with success status
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        if db_user.phone_verified:
            return {"success": True, "message": "Phone already verified"}

        if not db_user.phone_verification_code:
            raise ValueError("No verification code found. Please request a new one.")

        if datetime.utcnow() > db_user.phone_verification_expires:
            raise ValueError("Verification code expired. Please request a new one.")

        if db_user.phone_verification_code != code:
            raise ValueError("Invalid verification code")

        # Mark phone as verified and clear code
        db_user.phone_verified = True
        db_user.phone_verification_code = None
        db_user.phone_verification_expires = None
        self.db.commit()

        return {"success": True, "message": "Phone verified successfully"}


class CompleteOnboardingUseCase:
    """
    Use case for completing the onboarding process.
    """

    def __init__(self, user_repository: UserRepository, db: Session):
        self.user_repository = user_repository
        self.db = db

    def execute(self, user_id: UUID) -> dict:
        """
        Mark onboarding as complete.

        Args:
            user_id: User's UUID

        Returns:
            Dict with success status
        """
        # Query UserModel directly to get a mutable ORM object
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            raise ValueError("User not found")

        # Check requirements
        if not db_user.email_verified:
            raise ValueError("Email must be verified first")

        if not db_user.inbox_prefix or not db_user.inbox_token:
            raise ValueError("Inbox address must be generated first")

        # Phone is optional but recommended
        # if not db_user.phone_verified:
        #     raise ValueError("Phone must be verified first")

        db_user.onboarding_completed = True
        self.db.commit()

        return {
            "success": True,
            "message": "Onboarding completed! Welcome to PAI.",
            "inbox_email": db_user.inbox_email
        }


class GetOnboardingStatusUseCase:
    """
    Use case for getting current onboarding status.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(self, user_id: UUID) -> dict:
        """
        Get current onboarding status.

        Args:
            user_id: User's UUID

        Returns:
            Dict with onboarding status
        """
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        return {
            "email": user.email,
            "email_verified": user.email_verified,
            "inbox_email": user.inbox_email,
            "inbox_prefix": user.inbox_prefix,
            "inbox_verified": user.inbox_verified,
            "phone_number": user.phone_number,
            "phone_verified": user.phone_verified,
            "onboarding_completed": user.onboarding_completed,
            "current_step": self._determine_current_step(user)
        }

    def _determine_current_step(self, user) -> int:
        """Determine which onboarding step the user is on."""
        if not user.email_verified:
            return 1  # Email verification
        if not user.inbox_prefix:
            return 2  # Inbox setup
        if not user.inbox_verified:
            return 3  # Inbox verification
        if not user.phone_number:
            return 4  # Phone setup
        if not user.phone_verified:
            return 4  # Phone verification
        if not user.onboarding_completed:
            return 5  # Complete
        return 0  # Done
