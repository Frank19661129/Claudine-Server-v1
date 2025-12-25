"""
MCP Distributor - Central router for all MCP tool calls.

Routes requests to appropriate MCP servers (Google, Microsoft, etc.)
AND internal handlers (Tasks, Notes, Inbox, Persons).

Provides unified interface regardless of input source (command, chat, voice).

Supports test modes:
- test_mode=0: Normal execution (no logging)
- test_mode=1: Console logging only, NO execution
- test_mode=2: Console logging + require confirmation, execute only on confirm
"""
import httpx
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class InputSource(Enum):
    """How the request originated"""
    COMMAND = "command"      # #calendar, #task, etc.
    CHAT = "chat"           # Natural language via Claude
    VOICE = "voice"         # Voice input
    API = "api"             # Direct API call


class MCPProvider(Enum):
    """Available MCP providers"""
    # External providers (separate Docker containers)
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    # Internal providers (handled by InternalMCPHandler)
    INTERNAL_TASKS = "internal_tasks"
    INTERNAL_NOTES = "internal_notes"
    INTERNAL_INBOX = "internal_inbox"
    INTERNAL_PERSONS = "internal_persons"


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
    - #task command → MCPDistributor → Internal Tasks handler
    - Chat about appointments → MCPDistributor → Google/Microsoft MCP
    - Chat about tasks → MCPDistributor → Internal Tasks handler
    - Voice command → MCPDistributor → appropriate handler
    """

    # External MCP Server endpoints
    # Using Docker container names on pai-mcp-network
    MCP_SERVERS = {
        MCPProvider.GOOGLE: "http://pai-pai-google-office-1:8002",
        MCPProvider.MICROSOFT: "http://pai-pai-microsoft-office-1:8001",
    }

    # Internal providers don't need URLs - they use direct handlers
    INTERNAL_PROVIDERS = {
        MCPProvider.INTERNAL_TASKS,
        MCPProvider.INTERNAL_NOTES,
        MCPProvider.INTERNAL_INBOX,
        MCPProvider.INTERNAL_PERSONS,
    }

    def __init__(self, primary_provider: Optional[str] = None, db: Optional[Session] = None):
        """
        Initialize distributor.

        Args:
            primary_provider: Default provider for calendar (google/microsoft)
            db: Database session for internal handlers
        """
        self.primary_provider = primary_provider or "microsoft"
        self.db = db
        self._internal_handler = None

    def _get_internal_handler(self):
        """Lazy-load internal handler with database session."""
        if self._internal_handler is None and self.db is not None:
            from app.infrastructure.services.internal_mcp_handler import InternalMCPHandler
            self._internal_handler = InternalMCPHandler(self.db)
        return self._internal_handler

    def _is_internal_tool(self, tool_name: str) -> bool:
        """Check if a tool is handled internally."""
        from app.infrastructure.services.internal_mcp_handler import InternalMCPHandler
        return InternalMCPHandler.get_tool_provider(tool_name) is not None

    def _get_internal_provider(self, tool_name: str) -> Optional[str]:
        """Get the internal provider for a tool."""
        from app.infrastructure.services.internal_mcp_handler import InternalMCPHandler
        return InternalMCPHandler.get_tool_provider(tool_name)

    async def route_and_execute(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        input_source: InputSource = InputSource.CHAT,
        original_input: str = "",
        provider: Optional[str] = None,
        test_mode: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> MCPExecutionResult:
        """
        Route tool call to appropriate handler and execute.

        Args:
            tool_name: Name of the tool to execute
            tool_params: Parameters for the tool
            user_id: User ID for authentication
            input_source: How the request originated
            original_input: Original user input for logging
            provider: Explicit provider or None for auto
            test_mode: 0=normal, 1=log only, 2=log+confirm
            db: Database session for internal tools

        Returns:
            MCPExecutionResult with data or error, plus route trace
        """
        # Use provided db or fall back to instance db
        if db is not None:
            self.db = db

        # Get test_mode from context if not explicitly provided
        from app.core.test_mode_context import get_test_mode
        if test_mode is None:
            test_mode = get_test_mode()

        request_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Determine which provider to use
        selected_provider = self._determine_provider(tool_name, provider, tool_params)
        is_internal = selected_provider.startswith("internal_")

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
        handler_type = "INTERNAL" if is_internal else "EXTERNAL"
        logger.info(f"[{request_id}] ROUTE ({handler_type}): {input_source.value} → {detected_intent} → {selected_provider}:{tool_name}")

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

        # Execute the tool
        try:
            if is_internal:
                result = await self._execute_internal_tool(
                    tool_name=tool_name,
                    tool_params=tool_params,
                    user_id=user_id,
                    request_id=request_id,
                )
            else:
                mcp_provider = MCPProvider(selected_provider)
                result = await self._execute_external_mcp_tool(
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
        db: Optional[Session] = None,
    ) -> MCPExecutionResult:
        """
        Execute after user confirmation (for test_mode=2).

        Args:
            tool_name: Name of the tool
            tool_params: Parameters for the tool
            user_id: User ID
            provider: Provider to use
            db: Database session for internal tools

        Returns:
            MCPExecutionResult with execution result
        """
        if db is not None:
            self.db = db

        selected_provider = self._determine_provider(tool_name, provider, tool_params)
        is_internal = selected_provider.startswith("internal_")
        request_id = str(uuid.uuid4())[:8]

        try:
            if is_internal:
                result = await self._execute_internal_tool(
                    tool_name=tool_name,
                    tool_params=tool_params,
                    user_id=user_id,
                    request_id=request_id,
                )
            else:
                mcp_provider = MCPProvider(selected_provider)
                result = await self._execute_external_mcp_tool(
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

    def _determine_provider(
        self,
        tool_name: str,
        explicit_provider: Optional[str],
        tool_params: Dict[str, Any]
    ) -> str:
        """
        Determine which provider to use for a tool.

        Priority:
        1. Check if tool is internal (tasks, notes, inbox, persons)
        2. Explicit provider parameter
        3. Provider in tool_params
        4. Primary/default provider (for calendar tools)
        """
        # First check if it's an internal tool
        internal_provider = self._get_internal_provider(tool_name)
        if internal_provider:
            return internal_provider

        # For external tools, check explicit provider
        if explicit_provider:
            return explicit_provider

        if "provider" in tool_params and tool_params["provider"]:
            return tool_params["provider"]

        return self.primary_provider

    def _detect_intent(self, tool_name: str) -> str:
        """Detect intent category from tool name."""
        intent_map = {
            # Calendar intents
            "create_calendar_event": "calendar:create",
            "list_calendar_events": "calendar:list",
            "create_reminder": "calendar:reminder",
            "update_calendar_event": "calendar:update",
            "delete_calendar_event": "calendar:delete",
            # Task intents
            "create_task": "task:create",
            "list_tasks": "task:list",
            "complete_task": "task:complete",
            "update_task": "task:update",
            "delete_task": "task:delete",
            # Note intents
            "create_note": "note:create",
            "list_notes": "note:list",
            "update_note": "note:update",
            "delete_note": "note:delete",
            # Person intents
            "create_person": "person:create",
            "list_persons": "person:list",
            # Inbox intents
            "list_inbox": "inbox:list",
        }
        return intent_map.get(tool_name, f"unknown:{tool_name}")

    async def _execute_internal_tool(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Execute an internal tool via InternalMCPHandler.

        Args:
            tool_name: Tool to execute
            tool_params: Tool parameters
            user_id: User ID
            request_id: Request ID for logging

        Returns:
            Result from internal handler
        """
        handler = self._get_internal_handler()
        if handler is None:
            raise Exception("No database session available for internal tools")

        logger.info(f"[{request_id}] Executing internal tool: {tool_name}")
        result = await handler.execute(tool_name, tool_params, user_id)
        logger.info(f"[{request_id}] Internal result: success={result.get('success')}")
        return result

    async def _execute_external_mcp_tool(
        self,
        mcp_provider: MCPProvider,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Execute tool on an external MCP server.

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

        logger.info(f"[{request_id}] Calling external MCP: {execute_url}")
        logger.debug(f"[{request_id}] Payload: {payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(execute_url, json=payload)

            if response.status_code != 200:
                raise Exception(f"MCP returned {response.status_code}: {response.text}")

            result = response.json()
            logger.info(f"[{request_id}] External MCP response: success={result.get('success')}")

            return result

    async def get_available_tools(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available tools from all sources.

        Args:
            provider: Specific provider or None for all

        Returns:
            List of tool definitions from external MCP servers + internal handlers
        """
        tools = []

        # Get internal tools
        if provider is None or provider.startswith("internal"):
            from app.infrastructure.services.internal_mcp_handler import InternalMCPHandler
            internal_tools = InternalMCPHandler.get_all_tools()
            if provider:
                # Filter to specific internal provider
                tools.extend([t for t in internal_tools if t.get("provider") == provider])
            else:
                tools.extend(internal_tools)

        # Get external tools
        external_providers = [MCPProvider.GOOGLE, MCPProvider.MICROSOFT]
        if provider and not provider.startswith("internal"):
            try:
                external_providers = [MCPProvider(provider)]
            except ValueError:
                pass

        for mcp_provider in external_providers:
            if mcp_provider in self.INTERNAL_PROVIDERS:
                continue
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
