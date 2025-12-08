"""
Calendar OAuth use cases.
Part of Application layer - orchestrates OAuth flow for calendar providers.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from app.infrastructure.services.google_oauth import GoogleOAuthService
from app.infrastructure.services.microsoft_oauth import MicrosoftOAuthService
from app.infrastructure.services.token_service_client import token_service_client
from app.infrastructure.repositories.oauth_token_repository import OAuthTokenRepository
from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository

logger = logging.getLogger(__name__)


class CalendarOAuthUseCases:
    """
    Use cases for calendar provider OAuth authentication.
    Handles device flow for both Google and Microsoft calendars.
    """

    def __init__(self, db: Session):
        self.db = db
        self.token_repo = OAuthTokenRepository(db)
        self.settings_repo = UserSettingsRepository(db)
        self.google_oauth = GoogleOAuthService()
        self.microsoft_oauth = MicrosoftOAuthService()

    async def start_google_oauth_flow(self, user_id: UUID) -> dict:
        """
        Start Google OAuth device flow.

        Args:
            user_id: User ID requesting OAuth

        Returns:
            Dict with user_code, verification_url, device_code, expires_in
        """
        flow_data = await self.google_oauth.start_device_flow()

        return {
            "provider": "google",
            "user_code": flow_data["user_code"],
            "verification_url": flow_data["verification_url"],
            "device_code": flow_data["device_code"],
            "expires_in": flow_data["expires_in"],
            "interval": flow_data["interval"],
        }

    async def start_microsoft_oauth_flow(self, user_id: UUID) -> dict:
        """
        Start Microsoft OAuth device flow.

        Args:
            user_id: User ID requesting OAuth

        Returns:
            Dict with user_code, verification_url, device_code, expires_in
        """
        flow_data = await self.microsoft_oauth.start_device_flow()

        return {
            "provider": "microsoft",
            "user_code": flow_data["user_code"],
            "verification_url": flow_data["verification_url"],
            "device_code": flow_data["device_code"],
            "expires_in": flow_data["expires_in"],
            "interval": flow_data["interval"],
            "message": flow_data.get("message", ""),
        }

    async def poll_google_oauth_token(
        self, user_id: UUID, device_code: str, set_as_primary: bool = False
    ) -> Optional[dict]:
        """
        Poll for Google OAuth token and save if successful.

        Args:
            user_id: User ID
            device_code: Device code from start flow
            set_as_primary: Whether to set Google as primary calendar provider (default: False)

        Returns:
            Dict with success status and provider info, or None if still pending
        """
        token_data = await self.google_oauth.poll_for_token(device_code)

        if token_data is None:
            # Still waiting for user authorization
            return None

        # Save token to local database
        self.token_repo.save_token(
            user_id=user_id,
            provider="google",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
        )

        # Sync token to token-service for MCP servers
        await token_service_client.sync_token(
            user_id=str(user_id),
            provider="google",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
            service="calendar",
        )
        logger.info(f"Google OAuth token synced to token-service for user {user_id}")

        # Set as primary provider if requested OR if no primary provider exists yet
        settings = self.settings_repo.get_or_create_settings(user_id)
        if set_as_primary or not settings.primary_calendar_provider:
            self.settings_repo.update_primary_provider(user_id, "google")

        return {
            "success": True,
            "provider": "google",
            "expires_at": token_data.get("expires_at").isoformat() if token_data.get("expires_at") else None,
        }

    async def poll_microsoft_oauth_token(
        self, user_id: UUID, device_code: str, set_as_primary: bool = False
    ) -> Optional[dict]:
        """
        Poll for Microsoft OAuth token and save if successful.

        Args:
            user_id: User ID
            device_code: Device code from start flow
            set_as_primary: Whether to set Microsoft as primary calendar provider (default: False)

        Returns:
            Dict with success status and provider info, or None if still pending
        """
        token_data = await self.microsoft_oauth.poll_for_token(device_code)

        if token_data is None:
            # Still waiting for user authorization
            return None

        # Save token to local database
        self.token_repo.save_token(
            user_id=user_id,
            provider="microsoft",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
        )

        # Sync token to token-service for MCP servers
        await token_service_client.sync_token(
            user_id=str(user_id),
            provider="microsoft",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=token_data.get("expires_at"),
            service="calendar",
        )
        logger.info(f"Microsoft OAuth token synced to token-service for user {user_id}")

        # Set as primary provider if requested OR if no primary provider exists yet
        settings = self.settings_repo.get_or_create_settings(user_id)
        if set_as_primary or not settings.primary_calendar_provider:
            self.settings_repo.update_primary_provider(user_id, "microsoft")

        return {
            "success": True,
            "provider": "microsoft",
            "expires_at": token_data.get("expires_at").isoformat() if token_data.get("expires_at") else None,
        }

    def set_primary_provider(self, user_id: UUID, provider: str) -> dict:
        """
        Set a provider as the primary calendar.

        Args:
            user_id: User ID
            provider: Provider to set as primary (google or microsoft)

        Returns:
            Dict with success status

        Raises:
            ValueError: If provider is not connected
        """
        # Verify provider is connected
        token = self.token_repo.get_token(user_id, provider)
        if not token:
            raise ValueError(f"Provider {provider} is not connected")

        # Set as primary
        self.settings_repo.update_primary_provider(user_id, provider)

        return {
            "success": True,
            "provider": provider,
            "message": f"{provider.capitalize()} set as primary calendar provider",
        }

    async def disconnect_provider(self, user_id: UUID, provider: str) -> bool:
        """
        Disconnect a calendar provider (revoke token).

        Args:
            user_id: User ID
            provider: Provider to disconnect (google or microsoft)

        Returns:
            True if successfully disconnected
        """
        # Delete token from local database
        deleted = self.token_repo.delete_token(user_id, provider)

        # Also delete from token-service
        await token_service_client.delete_token(
            user_id=str(user_id),
            provider=provider,
            service="calendar",
        )
        logger.info(f"Token deleted from token-service for user {user_id}, provider {provider}")

        if not deleted:
            raise ValueError(f"Provider {provider} not connected")

        # If this was the primary provider, clear it
        settings = self.settings_repo.get_settings(user_id)
        if settings and settings.primary_calendar_provider == provider:
            # Check if user has another provider
            all_tokens = self.token_repo.get_all_tokens(user_id)
            if all_tokens:
                # Set another provider as primary
                other_provider = all_tokens[0].provider
                self.settings_repo.update_primary_provider(user_id, other_provider)
            else:
                # No providers left
                self.settings_repo.update_primary_provider(user_id, None)

        return True

    def get_connected_providers(self, user_id: UUID) -> list[dict]:
        """
        Get all connected calendar providers for a user.

        Args:
            user_id: User ID

        Returns:
            List of dicts with provider info (provider, expires_at, is_expired, is_primary)
        """
        tokens = self.token_repo.get_all_tokens(user_id)
        settings = self.settings_repo.get_settings(user_id)
        primary_provider = settings.primary_calendar_provider if settings else None

        result = []
        for token in tokens:
            result.append({
                "provider": token.provider,
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "is_expired": self.token_repo.is_token_expired(token),
                "is_primary": token.provider == primary_provider,
                "connected_at": token.created_at.isoformat() if token.created_at else None,
            })

        return result

    async def refresh_token_if_needed(self, user_id: UUID, provider: str) -> str:
        """
        Refresh access token if expired.

        Args:
            user_id: User ID
            provider: Provider (google or microsoft)

        Returns:
            Valid access token

        Raises:
            Exception: If refresh fails or token doesn't exist
        """
        token = self.token_repo.get_token(user_id, provider)

        if not token:
            raise Exception(f"No {provider} token found for user")

        # Check if token is expired
        if not self.token_repo.is_token_expired(token):
            return token.access_token

        # Token is expired, refresh it
        if not token.refresh_token:
            raise Exception(f"{provider} token expired and no refresh token available")

        if provider == "google":
            new_token_data = await self.google_oauth.refresh_access_token(token.refresh_token)
        elif provider == "microsoft":
            new_token_data = await self.microsoft_oauth.refresh_access_token(token.refresh_token)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        # Update stored token in local database
        self.token_repo.save_token(
            user_id=user_id,
            provider=provider,
            access_token=new_token_data["access_token"],
            refresh_token=new_token_data.get("refresh_token", token.refresh_token),
            expires_at=new_token_data.get("expires_at"),
        )

        # Sync refreshed token to token-service
        await token_service_client.sync_token(
            user_id=str(user_id),
            provider=provider,
            access_token=new_token_data["access_token"],
            refresh_token=new_token_data.get("refresh_token", token.refresh_token),
            expires_at=new_token_data.get("expires_at"),
            service="calendar",
        )
        logger.info(f"Refreshed token synced to token-service for user {user_id}, provider {provider}")

        return new_token_data["access_token"]
