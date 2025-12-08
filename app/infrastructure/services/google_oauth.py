"""
Google OAuth device flow service.
Part of Infrastructure layer.
"""
import httpx
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings


class GoogleOAuthService:
    """
    Google OAuth 2.0 device flow for calendar authentication.
    Used for devices with limited input capabilities (TV-style flow).
    """

    DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        # Note: calendar.events is included in calendar scope
        # Device flow doesn't support calendar.events as separate scope
    ]

    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET

    async def start_device_flow(self) -> dict:
        """
        Start Google OAuth device flow.

        Returns:
            Dict with device_code, user_code, verification_url, expires_in, interval

        Raises:
            Exception: If device flow initiation fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.DEVICE_CODE_URL,
                data={
                    "client_id": self.client_id,
                    "scope": " ".join(self.SCOPES),
                },
            )

            if response.status_code != 200:
                raise Exception(f"Google device flow failed: {response.text}")

            data = response.json()

            return {
                "device_code": data["device_code"],
                "user_code": data["user_code"],
                "verification_url": data["verification_url"],
                "expires_in": data["expires_in"],
                "interval": data.get("interval", 5),
            }

    async def poll_for_token(self, device_code: str) -> Optional[dict]:
        """
        Poll Google for OAuth token using device code.

        Args:
            device_code: Device code from start_device_flow()

        Returns:
            Dict with access_token, refresh_token, expires_in, scope if successful
            None if user hasn't authorized yet (authorization_pending)

        Raises:
            Exception: If polling fails with error other than authorization_pending
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

            data = response.json()

            # Check for errors
            if "error" in data:
                error = data["error"]

                # authorization_pending means user hasn't authorized yet - not an error
                if error == "authorization_pending":
                    return None

                # slow_down means we're polling too fast
                if error == "slow_down":
                    return None

                # expired_token means device code expired
                if error == "expired_token":
                    raise Exception("Device code expired. Please start flow again.")

                # access_denied means user denied access
                if error == "access_denied":
                    raise Exception("User denied access")

                # Other error
                raise Exception(f"Google token poll failed: {error}")

            # Success - return token data
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "expires_at": expires_at,
                "scope": data.get("scope"),
                "token_type": data.get("token_type", "Bearer"),
            }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Refresh Google OAuth access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Dict with new access_token and expires_at

        Raises:
            Exception: If refresh fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Google token refresh failed: {response.text}")

            data = response.json()
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "expires_at": expires_at,
                "token_type": data.get("token_type", "Bearer"),
            }
