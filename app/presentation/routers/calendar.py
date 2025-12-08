"""
Calendar router - OAuth and CRUD endpoints.
Part of Presentation layer.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.dependencies import get_db, get_current_user
from app.application.use_cases.calendar_oauth_use_cases import CalendarOAuthUseCases
from app.application.use_cases.calendar_event_use_cases import CalendarEventUseCases
from app.infrastructure.services.token_service_client import token_service_client
from app.infrastructure.repositories.oauth_token_repository import OAuthTokenRepository


router = APIRouter(prefix="/calendar", tags=["calendar"])


# ==================== Request/Response Models ====================


class OAuthStartResponse(BaseModel):
    """Response for starting OAuth flow."""
    provider: str
    user_code: str
    verification_url: str
    device_code: str
    expires_in: int
    interval: int
    message: Optional[str] = None


class OAuthPollRequest(BaseModel):
    """Request for polling OAuth token."""
    device_code: str
    set_as_primary: bool = False


class OAuthPollResponse(BaseModel):
    """Response for polling OAuth token."""
    success: bool
    provider: str
    expires_at: Optional[str] = None
    pending: bool = False


class ConnectedProvider(BaseModel):
    """Connected provider information."""
    provider: str
    expires_at: Optional[str]
    is_expired: bool
    is_primary: bool
    connected_at: Optional[str]


class CalendarInfo(BaseModel):
    """Calendar information."""
    id: str
    name: str
    provider: str
    is_primary: bool


class EventCreateRequest(BaseModel):
    """Request to create calendar event."""
    title: str = Field(..., min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    description: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, max_length=500)
    attendees: Optional[list[str]] = None
    is_all_day: bool = False
    provider: Optional[str] = None
    calendar_id: Optional[str] = None


class EventUpdateRequest(BaseModel):
    """Request to update calendar event."""
    title: str = Field(..., min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    description: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, max_length=500)
    provider: Optional[str] = None
    calendar_id: Optional[str] = None


class EventResponse(BaseModel):
    """Calendar event response."""
    id: Optional[str]
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    provider: str
    provider_calendar_id: Optional[str]
    attendees: list[str]
    is_all_day: bool

    class Config:
        from_attributes = True


# ==================== OAuth Endpoints ====================


@router.post("/oauth/google/start", response_model=OAuthStartResponse)
async def start_google_oauth(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start Google OAuth device flow.
    User should visit the verification_url and enter the user_code.
    Then poll /oauth/google/poll with the device_code.
    """
    try:
        use_cases = CalendarOAuthUseCases(db)
        result = await use_cases.start_google_oauth_flow(current_user["id"])
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start Google OAuth: {str(e)}",
        )


@router.post("/oauth/google/poll", response_model=OAuthPollResponse)
async def poll_google_oauth(
    request: OAuthPollRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Poll for Google OAuth token.
    Returns success: true when user has authorized.
    Returns pending: true while waiting for user authorization.
    """
    try:
        use_cases = CalendarOAuthUseCases(db)
        result = await use_cases.poll_google_oauth_token(
            user_id=current_user["id"],
            device_code=request.device_code,
            set_as_primary=request.set_as_primary,
        )

        if result is None:
            # Still pending
            return OAuthPollResponse(
                success=False,
                provider="google",
                pending=True,
            )

        return OAuthPollResponse(**result, pending=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to poll Google OAuth: {str(e)}",
        )


@router.post("/oauth/microsoft/start", response_model=OAuthStartResponse)
async def start_microsoft_oauth(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start Microsoft OAuth device flow.
    User should visit the verification_url and enter the user_code.
    Then poll /oauth/microsoft/poll with the device_code.
    """
    try:
        use_cases = CalendarOAuthUseCases(db)
        result = await use_cases.start_microsoft_oauth_flow(current_user["id"])
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start Microsoft OAuth: {str(e)}",
        )


@router.post("/oauth/microsoft/poll", response_model=OAuthPollResponse)
async def poll_microsoft_oauth(
    request: OAuthPollRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Poll for Microsoft OAuth token.
    Returns success: true when user has authorized.
    Returns pending: true while waiting for user authorization.
    """
    try:
        use_cases = CalendarOAuthUseCases(db)
        result = await use_cases.poll_microsoft_oauth_token(
            user_id=current_user["id"],
            device_code=request.device_code,
            set_as_primary=request.set_as_primary,
        )

        if result is None:
            # Still pending
            return OAuthPollResponse(
                success=False,
                provider="microsoft",
                pending=True,
            )

        return OAuthPollResponse(**result, pending=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to poll Microsoft OAuth: {str(e)}",
        )


@router.delete("/oauth/{provider}")
async def disconnect_provider(
    provider: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disconnect a calendar provider.
    Revokes OAuth token and removes from database.
    """
    if provider not in ["google", "microsoft"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider must be 'google' or 'microsoft'",
        )

    try:
        use_cases = CalendarOAuthUseCases(db)
        success = await use_cases.disconnect_provider(current_user["id"], provider)
        return {"success": success, "message": f"{provider} disconnected"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect {provider}: {str(e)}",
        )


@router.post("/oauth/{provider}/primary")
async def set_primary_provider(
    provider: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set a calendar provider as primary.
    The primary provider is used when no provider is specified in calendar operations.
    """
    if provider not in ["google", "microsoft"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider must be 'google' or 'microsoft'",
        )

    try:
        use_cases = CalendarOAuthUseCases(db)
        result = use_cases.set_primary_provider(current_user["id"], provider)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set primary provider: {str(e)}",
        )


@router.get("/oauth/connected", response_model=list[ConnectedProvider])
async def get_connected_providers(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all connected calendar providers for the current user.
    """
    try:
        use_cases = CalendarOAuthUseCases(db)
        providers = use_cases.get_connected_providers(current_user["id"])
        return providers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connected providers: {str(e)}",
        )


# ==================== Calendar Endpoints ====================


@router.get("/calendars", response_model=list[CalendarInfo])
async def list_calendars(
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List available calendars.
    If provider is not specified, uses primary calendar provider.
    """
    try:
        use_cases = CalendarEventUseCases(db)
        calendars = await use_cases.list_calendars(
            user_id=current_user["id"],
            provider=provider,
        )
        return calendars
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list calendars: {str(e)}",
        )


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    provider: Optional[str] = None,
    calendar_id: Optional[str] = None,
    max_results: int = 100,
    time_min: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List calendar events.
    If provider is not specified, uses primary calendar provider.
    If calendar_id is not specified, uses default calendar.
    """
    try:
        use_cases = CalendarEventUseCases(db)
        events = await use_cases.list_events(
            user_id=current_user["id"],
            provider=provider,
            calendar_id=calendar_id,
            max_results=max_results,
            time_min=time_min,
        )
        return [EventResponse.model_validate(event) for event in events]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list events: {str(e)}",
        )


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: EventCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new calendar event.
    If provider is not specified, uses primary calendar provider.
    """
    try:
        use_cases = CalendarEventUseCases(db)
        event = await use_cases.create_event(
            user_id=current_user["id"],
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
            location=request.location,
            attendees=request.attendees,
            is_all_day=request.is_all_day,
            provider=request.provider,
            calendar_id=request.calendar_id,
        )
        return EventResponse.model_validate(event)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}",
        )


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    request: EventUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing calendar event.
    If provider is not specified, uses primary calendar provider.
    """
    try:
        use_cases = CalendarEventUseCases(db)
        event = await use_cases.update_event(
            user_id=current_user["id"],
            event_id=event_id,
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
            location=request.location,
            provider=request.provider,
            calendar_id=request.calendar_id,
        )
        return EventResponse.model_validate(event)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update event: {str(e)}",
        )


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    provider: Optional[str] = None,
    calendar_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a calendar event.
    If provider is not specified, uses primary calendar provider.
    """
    try:
        use_cases = CalendarEventUseCases(db)
        success = await use_cases.delete_event(
            user_id=current_user["id"],
            event_id=event_id,
            provider=provider,
            calendar_id=calendar_id,
        )
        return {"success": success, "message": "Event deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}",
        )


# ==================== Token Sync Endpoint ====================


@router.post("/oauth/sync-tokens")
async def sync_tokens_to_service(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sync existing OAuth tokens to the token-service.

    This is a one-time sync for tokens that were stored before the token-service
    was integrated. MCP servers need tokens to be in the token-service.
    """
    try:
        token_repo = OAuthTokenRepository(db)
        tokens = token_repo.get_all_tokens(current_user["id"])

        synced = []
        for token in tokens:
            success = await token_service_client.sync_token(
                user_id=str(current_user["id"]),
                provider=token.provider,
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
                service="calendar",
            )
            if success:
                synced.append(token.provider)

        return {
            "success": True,
            "synced_providers": synced,
            "message": f"Synced {len(synced)} tokens to token-service",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync tokens: {str(e)}",
        )


# ==================== Token Refresh Endpoint (for MCP servers) ====================


class TokenRefreshRequest(BaseModel):
    """Request to refresh a token."""
    user_id: str
    provider: str  # google or microsoft


@router.post("/oauth/refresh-token")
async def refresh_token_for_mcp(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Refresh an OAuth token and sync to token-service.

    This endpoint is called by MCP servers when they get a 401 error.
    It refreshes the token using the stored refresh_token and syncs
    the new access_token to the token-service.

    Note: This is an internal endpoint - no user auth required.
    Should only be accessible from internal Docker network.
    """
    try:
        from uuid import UUID
        user_uuid = UUID(request.user_id)

        use_cases = CalendarOAuthUseCases(db)
        new_access_token = await use_cases.refresh_token_if_needed(
            user_id=user_uuid,
            provider=request.provider,
        )

        return {
            "success": True,
            "access_token": new_access_token,
            "provider": request.provider,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}",
        )
