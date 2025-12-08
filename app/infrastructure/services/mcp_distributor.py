"""
MCP Distributor - Central router for all MCP tool calls.

Routes requests to appropriate MCP servers (Google, Microsoft, etc.)
Provides unified interface regardless of input source (command, chat, voice).

Supports test modes:
- test_mode=0: Normal execution (no logging)
- test_mode=1: Console logging only, NO execution
- test_mode=2: Console logging + require confirmation, execute only on confirm
"""
import httpx
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class InputSource(Enum):
    """How the request originated"""
    COMMAND = "command"      # #calendar, #task, etc.
    CHAT = "chat"           # Natural language via Claude
    VOICE = "voice"         # Voice input
    API = "api"             # Direct API call


class MCPProvider(Enum):
    """Available MCP providers"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    # Future: TASKS = "tasks", NOTES = "notes", etc.


@dataclass
class RouteTrace:
    """Trace of the routing decision for debugging/logging"""
    request_id: str
    timestamp: str
    input_source: str
    original_input: str
    detected_intent: str
    detected_provider: Optional[str]
    selected_mcp: str
    tool_name: str
    tool_params: Dict[str, Any]
    test_mode: int

    def to_console_log(self) -> Dict[str, Any]:
        """Format for F12 console display"""
        return {
            "🔍 ROUTE TRACE": {
                "request_id": self.request_id,
                "timestamp": self.timestamp,
                "path": f"{self.input_source} → {self.detected_intent} → {self.selected_mcp}:{self.tool_name}",
                "details": {
                    "input_source": self.input_source,
                    "original_input": self.original_input[:100] + "..." if len(self.original_input) > 100 else self.original_input,
                    "detected_intent": self.detected_intent,
                    "detected_provider": self.detected_provider,
                    "selected_mcp": self.selected_mcp,
                    "tool_name": self.tool_name,
                    "tool_params": self.tool_params,
                },
                "test_mode": self.test_mode,
            }
        }


@dataclass
class MCPExecutionResult:
    """Result from MCP tool execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    route_trace: Optional[RouteTrace] = None
    requires_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "requires_confirmation": self.requires_confirmation,
        }
        if self.route_trace:
            result["route_trace"] = self.route_trace.to_console_log()
        return result


class MCPDistributor:
    """
    Central router for MCP tool calls.

    All paths lead to Rome (MCP):
    - #calendar command → MCPDistributor → Google/Microsoft MCP
    - Chat about appointments → MCPDistributor → Google/Microsoft MCP
    - Voice command → MCPDistributor → Google/Microsoft MCP
    """

    # MCP Server endpoints
    # Using Docker container names on claudine-mcp-network
    # Internal ports: both use 8001/8002 inside containers
    MCP_SERVERS = {
        MCPProvider.GOOGLE: "http://claudine-claudine-google-office-1:8002",
        MCPProvider.MICROSOFT: "http://claudine-claudine-microsoft-office-1:8001",
    }

    def __init__(self, primary_provider: Optional[str] = None):
        """
        Initialize distributor.

        Args:
            primary_provider: Default provider when none specified (google/microsoft)
        """
        self.primary_provider = primary_provider or "microsoft"

    async def route_and_execute(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        input_source: InputSource = InputSource.CHAT,
        original_input: str = "",
        provider: Optional[str] = None,
        test_mode: Optional[int] = None,  # If None, read from context
    ) -> MCPExecutionResult:
        """
        Route tool call to appropriate MCP and execute.

        Args:
            tool_name: Name of the tool to execute (e.g., "create_calendar_event")
            tool_params: Parameters for the tool
            user_id: User ID for authentication
            input_source: How the request originated
            original_input: Original user input for logging
            provider: Explicit provider (google/microsoft) or None for auto
            test_mode: 0=normal, 1=log+execute, 2=log+confirm+execute

        Returns:
            MCPExecutionResult with data or error, plus route trace
        """
        # Get test_mode from context if not explicitly provided
        from app.core.test_mode_context import get_test_mode
        if test_mode is None:
            test_mode = get_test_mode()

        request_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Determine which MCP to use
        selected_provider = self._determine_provider(provider, tool_params)
        mcp_provider = MCPProvider(selected_provider)

        # Detect intent from tool name
        detected_intent = self._detect_intent(tool_name)

        # Build route trace
        route_trace = RouteTrace(
            request_id=request_id,
            timestamp=timestamp,
            input_source=input_source.value,
            original_input=original_input,
            detected_intent=detected_intent,
            detected_provider=provider,
            selected_mcp=selected_provider,
            tool_name=tool_name,
            tool_params=tool_params,
            test_mode=test_mode,
        )

        # Log the route
        logger.info(f"[{request_id}] ROUTE: {input_source.value} → {detected_intent} → {selected_provider}:{tool_name}")

        # Test mode 1: Log only, NO execution
        if test_mode == 1:
            return MCPExecutionResult(
                success=True,
                data={
                    "status": "test_mode",
                    "message": "Test mode: alleen logging, geen uitvoering",
                    "would_execute": {
                        "tool": tool_name,
                        "provider": selected_provider,
                        "params": tool_params,
                    }
                },
                route_trace=route_trace,
                requires_confirmation=False,
            )

        # Test mode 2: Return without executing, require confirmation
        if test_mode == 2:
            return MCPExecutionResult(
                success=True,
                data={"status": "awaiting_confirmation", "message": "Wacht op bevestiging..."},
                route_trace=route_trace,
                requires_confirmation=True,
            )

        # Test mode 0: Execute the tool via MCP
        try:
            result = await self._execute_mcp_tool(
                mcp_provider=mcp_provider,
                tool_name=tool_name,
                tool_params=tool_params,
                user_id=user_id,
                request_id=request_id,
            )

            return MCPExecutionResult(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
                route_trace=route_trace if test_mode >= 1 else None,
            )

        except Exception as e:
            logger.error(f"[{request_id}] MCP execution failed: {e}")
            return MCPExecutionResult(
                success=False,
                error=str(e),
                route_trace=route_trace if test_mode >= 1 else None,
            )

    async def confirm_and_execute(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        provider: Optional[str] = None,
    ) -> MCPExecutionResult:
        """
        Execute after user confirmation (for test_mode=2).

        Args:
            tool_name: Name of the tool
            tool_params: Parameters for the tool
            user_id: User ID
            provider: Provider to use

        Returns:
            MCPExecutionResult with execution result
        """
        selected_provider = self._determine_provider(provider, tool_params)
        mcp_provider = MCPProvider(selected_provider)
        request_id = str(uuid.uuid4())[:8]

        try:
            result = await self._execute_mcp_tool(
                mcp_provider=mcp_provider,
                tool_name=tool_name,
                tool_params=tool_params,
                user_id=user_id,
                request_id=request_id,
            )

            return MCPExecutionResult(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        except Exception as e:
            logger.error(f"[{request_id}] Confirmed execution failed: {e}")
            return MCPExecutionResult(
                success=False,
                error=str(e),
            )

    def _determine_provider(self, explicit_provider: Optional[str], tool_params: Dict[str, Any]) -> str:
        """
        Determine which provider to use.

        Priority:
        1. Explicit provider parameter
        2. Provider in tool_params
        3. Primary/default provider
        """
        if explicit_provider:
            return explicit_provider

        if "provider" in tool_params and tool_params["provider"]:
            return tool_params["provider"]

        return self.primary_provider

    def _detect_intent(self, tool_name: str) -> str:
        """Detect intent category from tool name."""
        intent_map = {
            "create_calendar_event": "calendar:create",
            "list_calendar_events": "calendar:list",
            "create_reminder": "calendar:reminder",
            "update_calendar_event": "calendar:update",
            "delete_calendar_event": "calendar:delete",
            # Future intents
            "create_task": "task:create",
            "list_tasks": "task:list",
            "create_note": "note:create",
        }
        return intent_map.get(tool_name, f"unknown:{tool_name}")

    async def _execute_mcp_tool(
        self,
        mcp_provider: MCPProvider,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Execute tool on the appropriate MCP server.

        Args:
            mcp_provider: Which MCP server to call
            tool_name: Tool to execute
            tool_params: Tool parameters
            user_id: User ID for auth
            request_id: Request ID for logging

        Returns:
            Response from MCP server
        """
        mcp_url = self.MCP_SERVERS[mcp_provider]
        execute_url = f"{mcp_url}/execute"

        payload = {
            "tool_name": tool_name,
            "params": tool_params,
            "user_id": user_id,
            "request_id": request_id,
        }

        logger.info(f"[{request_id}] Calling MCP: {execute_url}")
        logger.debug(f"[{request_id}] Payload: {payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(execute_url, json=payload)

            if response.status_code != 200:
                raise Exception(f"MCP returned {response.status_code}: {response.text}")

            result = response.json()
            logger.info(f"[{request_id}] MCP response: success={result.get('success')}")

            return result

    async def get_available_tools(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available tools from MCP servers.

        Args:
            provider: Specific provider or None for all

        Returns:
            List of tool definitions
        """
        tools = []

        providers = [MCPProvider(provider)] if provider else list(MCPProvider)

        for mcp_provider in providers:
            try:
                mcp_url = self.MCP_SERVERS[mcp_provider]
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{mcp_url}/tools")
                    if response.status_code == 200:
                        data = response.json()
                        for tool in data.get("tools", []):
                            tool["provider"] = mcp_provider.value
                            tools.append(tool)
            except Exception as e:
                logger.warning(f"Could not get tools from {mcp_provider.value}: {e}")

        return tools
