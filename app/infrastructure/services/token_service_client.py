"""
Token Service Client - HTTP client for syncing tokens to the token-service.

Used to sync OAuth tokens to the token-service so MCP servers can access them.
"""
import httpx
import os
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Token service URL - uses Docker network
TOKEN_SERVICE_URL = os.getenv("TOKEN_SERVICE_URL", "http://token-service:8100")


class TokenServiceClient:
    """Client for syncing tokens to the central token-service."""

    def __init__(self, base_url: str = TOKEN_SERVICE_URL):
        self.base_url = base_url

    async def sync_token(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        scope: Optional[str] = None,
        service: str = "calendar",
    ) -> bool:
        """
        Sync a token to the token-service.

        This makes the token available to MCP servers.

        Args:
            user_id: User ID (UUID as string)
            provider: Provider name (google, microsoft)
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_at: Token expiration datetime
            scope: Token scopes
            service: Service type (default: calendar)

        Returns:
            True if sync successful, False otherwise
        """
        payload = {
            "user_id": str(user_id),
            "provider": provider,
            "service": service,
            "access_token": access_token,
            "token_type": "Bearer",
        }

        if refresh_token:
            payload["refresh_token"] = refresh_token
        if expires_at:
            payload["expires_at"] = expires_at.isoformat()
        if scope:
            payload["scope"] = scope

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.base_url}/tokens",
                    json=payload
                )

                if response.status_code in (200, 201):
                    logger.info(f"Token synced to token-service: user={user_id}, provider={provider}, service={service}")
                    return True
                else:
                    logger.error(f"Token sync failed: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Token sync error: {e}")
            return False

    async def delete_token(
        self,
        user_id: str,
        provider: str,
        service: str = "calendar",
    ) -> bool:
        """
        Delete a token from the token-service.

        Args:
            user_id: User ID
            provider: Provider name
            service: Service type

        Returns:
            True if delete successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.delete(
                    f"{self.base_url}/tokens/{user_id}/{provider}/{service}"
                )

                if response.status_code in (200, 204, 404):
                    logger.info(f"Token deleted from token-service: user={user_id}, provider={provider}")
                    return True
                else:
                    logger.error(f"Token delete failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Token delete error: {e}")
            return False


# Singleton instance
token_service_client = TokenServiceClient()
