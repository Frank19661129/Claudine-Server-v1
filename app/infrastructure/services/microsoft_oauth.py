"""
Microsoft OAuth device flow service.
Part of Infrastructure layer.
"""
import httpx
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings


class MicrosoftOAuthService:
    """
    Microsoft OAuth 2.0 device flow for calendar authentication.
    Used for devices with limited input capabilities (TV-style flow).
    """

    SCOPES = [
        "Calendars.ReadWrite",
        "User.Read",
        "offline_access",
    ]

    def __init__(self):
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

    async def start_device_flow(self) -> dict:
        """
        Start Microsoft OAuth device flow.

        Returns:
            Dict with device_code, user_code, verification_uri, expires_in, interval

        Raises:
            Exception: If device flow initiation fails
        """
        url = f"{self.authority}/oauth2/v2.0/devicecode"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "client_id": self.client_id,
                    "scope": " ".join(self.SCOPES),
                },
            )

            if response.status_code != 200:
                raise Exception(f"Microsoft device flow failed: {response.text}")

            data = response.json()

            return {
                "device_code": data["device_code"],
                "user_code": data["user_code"],
                "verification_url": data["verification_uri"],
                "expires_in": data["expires_in"],
                "interval": data.get("interval", 5),
                "message": data.get("message", ""),
            }

    async def poll_for_token(self, device_code: str) -> Optional[dict]:
        """
        Poll Microsoft for OAuth token using device code.

        Args:
            device_code: Device code from start_device_flow()

        Returns:
            Dict with access_token, refresh_token, expires_in, scope if successful
            None if user hasn't authorized yet (authorization_pending)

        Raises:
            Exception: If polling fails with error other than authorization_pending
        """
        url = f"{self.authority}/oauth2/v2.0/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "client_id": self.client_id,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
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

                # authorization_declined means user denied access
                if error == "authorization_declined":
                    raise Exception("User denied access")

                # Other error
                raise Exception(f"Microsoft token poll failed: {error}")

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
        Refresh Microsoft OAuth access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Dict with new access_token and expires_at

        Raises:
            Exception: If refresh fails
        """
        url = f"{self.authority}/oauth2/v2.0/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "client_id": self.client_id,
                    # Note: device flow is a public client - do NOT send client_secret
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": " ".join(self.SCOPES),
                },
            )

            if response.status_code != 200:
                raise Exception(f"Microsoft token refresh failed: {response.text}")

            data = response.json()
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", refresh_token),  # May return new refresh token
                "expires_at": expires_at,
                "token_type": data.get("token_type", "Bearer"),
            }
