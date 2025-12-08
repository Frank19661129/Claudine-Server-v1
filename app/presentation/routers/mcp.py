"""
MCP Router - Unified MCP tool execution endpoint.

All paths lead to Rome (MCP):
- Commands (#calendar, #task) → this endpoint
- Chat tool calls → this endpoint
- Direct API calls → this endpoint

Supports test modes via test_mode parameter:
- 0: Normal execution
- 1: Console logging + execute
- 2: Console logging + require confirmation
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.dependencies import get_db, get_current_user
from app.infrastructure.services.mcp_distributor import MCPDistributor, InputSource
from app.infrastructure.services.intent_detector import IntentDetector
from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ==================== Request/Response Models ====================


class MCPExecuteRequest(BaseModel):
    """Request to execute an MCP tool."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    provider: Optional[str] = Field(None, description="Explicit provider: google or microsoft")
    input_source: str = Field(default="api", description="Source: command, chat, voice, api")
    original_input: Optional[str] = Field(None, description="Original user input for logging")
    test_mode: int = Field(default=0, ge=0, le=2, description="Test mode: 0=normal, 1=log, 2=confirm")


class MCPConfirmRequest(BaseModel):
    """Request to confirm and execute a pending MCP operation."""
    tool_name: str
    tool_params: Dict[str, Any]
    provider: Optional[str] = None


class DetectIntentRequest(BaseModel):
    """Request to detect intent from user input."""
    user_input: str = Field(..., min_length=1, max_length=5000)


class RouteTraceResponse(BaseModel):
    """Route trace for debugging."""
    request_id: str
    timestamp: str
    path: str
    details: Dict[str, Any]
    test_mode: int


class MCPExecuteResponse(BaseModel):
    """Response from MCP execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    route_trace: Optional[Dict[str, Any]] = None


class DetectIntentResponse(BaseModel):
    """Response from intent detection."""
    intent_type: str
    confidence: float
    source: str
    provider: Optional[str]
    extracted_params: Dict[str, Any]
    needs_claude_extraction: bool
    date_context: Dict[str, Any]


# ==================== Endpoints ====================


@router.post("/execute", response_model=MCPExecuteResponse)
async def execute_mcp_tool(
    request: MCPExecuteRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute an MCP tool.

    This is the unified endpoint for all MCP operations.
    All paths (commands, chat, voice) should route through here.

    Test modes:
    - test_mode=0: Normal execution
    - test_mode=1: Log route trace + execute
    - test_mode=2: Log route trace + return for confirmation (don't execute yet)
    """
    try:
        # Get user's primary calendar provider from settings
        settings_repo = UserSettingsRepository(db)
        settings = settings_repo.get_settings(current_user["id"])
        primary_provider = settings.primary_calendar_provider if settings else "microsoft"

        # Create distributor with user's primary provider and database session
        distributor = MCPDistributor(primary_provider=primary_provider, db=db)

        # Map input source string to enum
        source_map = {
            "command": InputSource.COMMAND,
            "chat": InputSource.CHAT,
            "voice": InputSource.VOICE,
            "api": InputSource.API,
        }
        input_source = source_map.get(request.input_source, InputSource.API)

        # Execute via distributor (db passed for internal tools like tasks, notes, etc.)
        result = await distributor.route_and_execute(
            tool_name=request.tool_name,
            tool_params=request.tool_params,
            user_id=str(current_user["id"]),
            input_source=input_source,
            original_input=request.original_input or "",
            provider=request.provider,
            test_mode=request.test_mode,
            db=db,
        )

        return MCPExecuteResponse(
            success=result.success,
            data=result.data,
            error=result.error,
            requires_confirmation=result.requires_confirmation,
            route_trace=result.route_trace.to_console_log() if result.route_trace else None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP execution failed: {str(e)}",
        )


@router.post("/confirm", response_model=MCPExecuteResponse)
async def confirm_mcp_execution(
    request: MCPConfirmRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and execute a pending MCP operation.

    Use this after receiving requires_confirmation=true from /execute with test_mode=2.
    """
    try:
        # Get user's primary calendar provider
        settings_repo = UserSettingsRepository(db)
        settings = settings_repo.get_settings(current_user["id"])
        primary_provider = settings.primary_calendar_provider if settings else "microsoft"

        distributor = MCPDistributor(primary_provider=primary_provider, db=db)

        result = await distributor.confirm_and_execute(
            tool_name=request.tool_name,
            tool_params=request.tool_params,
            user_id=str(current_user["id"]),
            provider=request.provider,
            db=db,
        )

        return MCPExecuteResponse(
            success=result.success,
            data=result.data,
            error=result.error,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP confirmation failed: {str(e)}",
        )


@router.post("/detect-intent", response_model=DetectIntentResponse)
async def detect_intent(
    request: DetectIntentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Detect intent from user input.

    Use this to understand what the user wants before executing.
    Returns intent type, confidence, detected provider, and date context.
    """
    try:
        detector = IntentDetector()
        intent = detector.detect(request.user_input)
        date_context = detector.get_date_context()

        return DetectIntentResponse(
            intent_type=intent.intent_type.value,
            confidence=intent.confidence,
            source=intent.source,
            provider=intent.provider,
            extracted_params=intent.extracted_params,
            needs_claude_extraction=intent.needs_claude_extraction,
            date_context=date_context,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intent detection failed: {str(e)}",
        )


@router.get("/tools")
async def list_available_tools(
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List available MCP tools.

    Returns tool definitions from all connected MCP servers,
    or from a specific provider if specified.
    """
    try:
        settings_repo = UserSettingsRepository(db)
        settings = settings_repo.get_settings(current_user["id"])
        primary_provider = settings.primary_calendar_provider if settings else "microsoft"

        distributor = MCPDistributor(primary_provider=primary_provider, db=db)
        tools = await distributor.get_available_tools(provider)

        return {
            "tools": tools,
            "primary_provider": primary_provider,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}",
        )


@router.get("/health")
async def mcp_health():
    """Check health of MCP servers."""
    import httpx
    from app.infrastructure.services.mcp_distributor import MCPDistributor, MCPProvider

    servers = {
        "google": f"{MCPDistributor.MCP_SERVERS[MCPProvider.GOOGLE]}/health",
        "microsoft": f"{MCPDistributor.MCP_SERVERS[MCPProvider.MICROSOFT]}/health",
    }

    results = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in servers.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    results[name] = {"status": "healthy", "data": response.json()}
                else:
                    results[name] = {"status": "unhealthy", "code": response.status_code}
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}

    all_healthy = all(r["status"] == "healthy" for r in results.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "servers": results,
    }
