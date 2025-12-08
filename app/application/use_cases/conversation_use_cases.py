"""
Conversation use cases.
Part of Application layer - orchestrates conversation operations.
"""
from typing import Optional, List, AsyncIterator
from uuid import UUID
from datetime import datetime
import json
from sqlalchemy.orm import Session

from app.domain.entities.conversation import Conversation, Message
from app.domain.services.command_parser import CommandParser, CommandType
from app.infrastructure.repositories.conversation_repository import ConversationRepository
from app.infrastructure.services.claude_service import ClaudeService
from app.infrastructure.services.widget_service import WidgetService
from app.application.use_cases.calendar_event_use_cases import CalendarEventUseCases


class ConversationUseCases:
    """
    Use cases for conversation management and AI chat.
    """

    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.claude_service = ClaudeService()
        self.command_parser = CommandParser()
        self.widget_service = WidgetService()

    def create_conversation(
        self,
        user_id: UUID,
        mode: str = "chat",
        title: Optional[str] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            mode: Conversation mode (chat, voice, note, scan)
            title: Optional custom title

        Returns:
            Created Conversation entity
        """
        # Use domain factory to validate
        conversation_entity = Conversation.create(
            user_id=user_id,
            mode=mode,
            title=title,
        )

        # Persist to database
        conversation_model = self.conversation_repo.create_conversation(
            user_id=user_id,
            title=conversation_entity.title,
            mode=mode,
            metadata={},
        )

        return self.conversation_repo.conversation_to_entity(conversation_model)

    def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> Optional[Conversation]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)

        Returns:
            Conversation entity or None
        """
        conversation_model = self.conversation_repo.get_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if not conversation_model:
            return None

        return self.conversation_repo.conversation_to_entity(conversation_model)

    def get_user_conversations(
        self,
        user_id: UUID,
        mode: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get all conversations for a user.

        Args:
            user_id: User ID
            mode: Optional filter by mode
            limit: Max results
            offset: Offset for pagination

        Returns:
            List of Conversation entities
        """
        conversation_models = self.conversation_repo.get_user_conversations(
            user_id=user_id,
            mode=mode,
            limit=limit,
            offset=offset,
        )

        return [
            self.conversation_repo.conversation_to_entity(model)
            for model in conversation_models
        ]

    async def send_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
        mode: Optional[str] = None,
    ) -> Message:
        """
        Send a message in a conversation and get AI response.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            content: Message content
            mode: Optional conversation mode override

        Returns:
            AI assistant response Message

        Raises:
            ValueError: If conversation not found or user doesn't have access
        """
        # Get conversation
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Check for commands
        parsed_command = self.command_parser.parse(content)

        # Save user message
        user_message = self.conversation_repo.add_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata={
                "command": parsed_command.command_type.value if parsed_command.is_command() else None,
                "command_params": parsed_command.parameters if parsed_command.is_command() else None,
            },
        )

        # Detect widget intent
        widget_intent = await self.widget_service.detect_widget_intent(content)
        widget_data = None

        # If widget detected, prepare widget data
        if widget_intent.widget_type and widget_intent.confidence >= 0.7:
            widget_data = await self.widget_service.create_widget_for_intent(widget_intent)

        # Handle special commands
        if parsed_command.is_command():
            response_content = await self._handle_command(parsed_command, conversation)
        else:
            # Get AI response
            response_content = await self._get_ai_response(conversation, mode or conversation.mode)

        # Save assistant response (with widget if available)
        assistant_message = self.conversation_repo.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_content,
            metadata={"widget": widget_data} if widget_data else None,
        )

        return Message(
            id=str(assistant_message.id),
            conversation_id=assistant_message.conversation_id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at,
            metadata=assistant_message.metadata or {},
        )

    async def send_message_stream(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
        mode: Optional[str] = None,
        test_mode: int = 0,
    ) -> AsyncIterator[str]:
        """
        Send a message and stream AI response.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            content: Message content
            mode: Optional conversation mode override
            test_mode: 0=normal, 1=log only, 2=log+confirm

        Yields:
            Text chunks from AI response

        Raises:
            ValueError: If conversation not found
        """
        # Store test_mode for use in tool execution
        self._test_mode = test_mode
        # Get conversation
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Check for commands
        parsed_command = self.command_parser.parse(content)

        # Save user message
        user_message = self.conversation_repo.add_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata={
                "command": parsed_command.command_type.value if parsed_command.is_command() else None,
                "command_params": parsed_command.parameters if parsed_command.is_command() else None,
            },
        )

        # Reload conversation to include the new user message
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Failed to reload conversation")

        # Detect widget intent before processing
        widget_intent = await self.widget_service.detect_widget_intent(content)
        widget_data = None

        # If widget detected, prepare widget data
        if widget_intent.widget_type and widget_intent.confidence >= 0.7:
            widget_data = await self.widget_service.create_widget_for_intent(widget_intent)

        # Handle commands or get AI response
        if parsed_command.is_command():
            response_content = await self._handle_command(parsed_command, conversation)
            # Save response (with widget if available)
            self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_content,
                metadata={"widget": widget_data} if widget_data else None,
            )
            yield response_content
        else:
            # Stream AI response
            full_response = ""
            async for chunk in self._get_ai_response_stream(conversation, mode or conversation.mode):
                full_response += chunk
                yield chunk

            # Save complete response (with widget if available)
            self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                metadata={"widget": widget_data} if widget_data else None,
            )

    async def _handle_command(self, parsed_command, conversation: Conversation) -> str:
        """Handle special commands."""
        if parsed_command.command_type == CommandType.HELP:
            topic = parsed_command.parameters.get("topic")
            if topic:
                # Create temp command to get its help text
                temp_cmd = type('obj', (object,), {'command_type': topic, 'get_help_text': lambda: CommandParser().parse(f"#{topic.value}").get_help_text()})()
                return temp_cmd.get_help_text()
            return parsed_command.get_help_text()

        elif parsed_command.command_type == CommandType.CALENDAR:
            # Use Claude to extract calendar event details from the command
            # Then route through MCP Distributor for test mode support
            try:
                from app.infrastructure.services.mcp_distributor import MCPDistributor, InputSource
                from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository
                from app.core.test_mode_context import get_test_mode

                today = datetime.now().strftime('%Y-%m-%d %H:%M')
                extraction_prompt = f"""Extract calendar event details from this request: "{parsed_command.original_text}"

Return JSON with:
- title (string, required)
- start_time (ISO 8601 datetime, required)
- end_time (ISO 8601 datetime, required)
- description (string, optional)
- location (string, optional)
- provider (string, optional - "google" or "microsoft" if mentioned)

Current date and time context: {today}
Use this as reference for relative dates like "morgen" (tomorrow), "volgende week" (next week), etc."""

                response = await self.claude_service.send_message(
                    messages=[{"role": "user", "content": extraction_prompt}],
                    system_prompt="You are a calendar assistant. Extract event details and respond with valid JSON only."
                )

                event_data = json.loads(response["content"][0]["text"])

                # Get user's primary calendar provider
                settings_repo = UserSettingsRepository(self.db)
                settings = settings_repo.get_settings(conversation.user_id)
                primary_provider = settings.primary_calendar_provider if settings else "microsoft"

                # Build tool params for MCP
                tool_params = {
                    "title": event_data["title"],
                    "start_time": event_data["start_time"],
                    "end_time": event_data["end_time"],
                    "description": event_data.get("description"),
                    "location": event_data.get("location"),
                    "provider": event_data.get("provider"),  # May override default
                }

                # Route through MCP Distributor (test_mode read from context)
                distributor = MCPDistributor(primary_provider=primary_provider)
                result = await distributor.route_and_execute(
                    tool_name="create_calendar_event",
                    tool_params=tool_params,
                    user_id=str(conversation.user_id),
                    input_source=InputSource.COMMAND,
                    original_input=parsed_command.original_text,
                    provider=tool_params.get("provider"),
                )

                # Get test_mode from context
                test_mode = get_test_mode()
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[#CALENDAR CMD] test_mode={test_mode}, result.success={result.success}, has_trace={result.route_trace is not None}, provider={tool_params.get('provider')}")

                # Handle test mode responses
                if test_mode == 1:
                    trace = result.route_trace
                    logger.info(f"[#CALENDAR CMD] test_mode=1, trace exists={trace is not None}")
                    if trace:
                        try:
                            params_json = json.dumps(trace.tool_params, indent=2, ensure_ascii=False)
                            msg = f"🔧 **TEST MODE: Alleen logging**\n\n" \
                                  f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                                  f"🔧 Tool: {trace.tool_name}\n" \
                                  f"📋 Parameters:\n```json\n{params_json}\n```\n\n" \
                                  f"⚠️ Geen uitvoering (test_mode=1)"
                            logger.info(f"[#CALENDAR CMD] Returning message, len={len(msg)}")
                            return msg
                        except Exception as format_err:
                            logger.error(f"[#CALENDAR CMD] Format error: {format_err}")
                            return f"🔧 Test mode: format error: {format_err}"
                    return "🔧 Test mode: geen uitvoering (no trace)"

                if test_mode == 2 and result.requires_confirmation:
                    trace = result.route_trace
                    if trace:
                        return f"🔧 **TEST MODE: Bevestiging vereist**\n\n" \
                               f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                               f"🔧 Tool: {trace.tool_name}\n" \
                               f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                               f"⏳ Wacht op bevestiging via popup..."
                    return "🔧 Wacht op bevestiging..."

                # Normal execution result
                if result.success and result.data:
                    provider_name = "Google Calendar" if tool_params.get("provider") == "google" else "Office 365"
                    return f"✅ Agenda-afspraak aangemaakt!\n\n📅 **{tool_params['title']}**\n🕐 {tool_params['start_time']} - {tool_params['end_time']}\n📍 {tool_params.get('location') or 'Geen locatie'}\n\nDe afspraak is toegevoegd aan je {provider_name}."
                else:
                    return f"❌ Kon de afspraak niet maken: {result.error}"

            except Exception as e:
                return f"❌ Kon de afspraak niet maken: {str(e)}\n\nZorg dat je een kalender hebt gekoppeld in Settings."

        elif parsed_command.command_type == CommandType.REMINDER:
            # Reminder is just like calendar but with a simpler message and 5 min duration
            # Routes through MCP Distributor for test mode support
            try:
                from datetime import timedelta
                from app.infrastructure.services.mcp_distributor import MCPDistributor, InputSource
                from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository
                from app.core.test_mode_context import get_test_mode

                today = datetime.now().strftime('%Y-%m-%d %H:%M')
                extraction_prompt = f"""Extract reminder/event details from this request: "{parsed_command.original_text}"

Return JSON with:
- title (string, required - just the title without emoji)
- start_time (ISO 8601 datetime, required)
- description (string, optional)
- location (string, optional)
- provider (string, optional - "google" or "microsoft" if mentioned)

Note: Do NOT include end_time - reminders are 5 minutes by default.

Current date and time context: {today}
Use this as reference for relative dates like "morgen" (tomorrow), "vanavond" (tonight), etc."""

                response = await self.claude_service.send_message(
                    messages=[{"role": "user", "content": extraction_prompt}],
                    system_prompt="You are a calendar assistant. Extract event details and respond with valid JSON only."
                )

                event_data = json.loads(response["content"][0]["text"])

                # Parse ISO 8601 datetime strings
                start_time = datetime.fromisoformat(event_data["start_time"].replace('Z', '+00:00'))
                # Reminders are 5 minutes long
                end_time = start_time + timedelta(minutes=5)

                # Add bell emoji to title
                title_with_icon = f"🔔 {event_data['title']}"

                # Get user's primary calendar provider
                settings_repo = UserSettingsRepository(self.db)
                settings = settings_repo.get_settings(conversation.user_id)
                primary_provider = settings.primary_calendar_provider if settings else "microsoft"

                # Build tool params for MCP
                tool_params = {
                    "title": title_with_icon,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "description": event_data.get("description"),
                    "location": event_data.get("location"),
                    "provider": event_data.get("provider"),  # May override default
                }

                # Route through MCP Distributor (test_mode read from context)
                distributor = MCPDistributor(primary_provider=primary_provider)
                result = await distributor.route_and_execute(
                    tool_name="create_reminder",
                    tool_params=tool_params,
                    user_id=str(conversation.user_id),
                    input_source=InputSource.COMMAND,
                    original_input=parsed_command.original_text,
                    provider=tool_params.get("provider"),
                )

                # Get test_mode from context
                test_mode = get_test_mode()

                # Handle test mode responses
                if test_mode == 1:
                    trace = result.route_trace
                    if trace:
                        return f"🔧 **TEST MODE: Alleen logging**\n\n" \
                               f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                               f"🔧 Tool: {trace.tool_name}\n" \
                               f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                               f"⚠️ Geen uitvoering (test_mode=1)"
                    return "🔧 Test mode: geen uitvoering"

                if test_mode == 2 and result.requires_confirmation:
                    trace = result.route_trace
                    if trace:
                        return f"🔧 **TEST MODE: Bevestiging vereist**\n\n" \
                               f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                               f"🔧 Tool: {trace.tool_name}\n" \
                               f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                               f"⏳ Wacht op bevestiging via popup..."
                    return "🔧 Wacht op bevestiging..."

                # Normal execution result
                if result.success and result.data:
                    return f"⏰ Herinnering aangemaakt!\n\n📝 {event_data['title']}\n🕐 {start_time.strftime('%d-%m-%Y %H:%M')}\n\nDe herinnering is toegevoegd aan je kalender."
                else:
                    return f"❌ Kon de herinnering niet maken: {result.error}"

            except Exception as e:
                return f"❌ Kon de herinnering niet maken: {str(e)}\n\nZorg dat je een kalender hebt gekoppeld in Settings."

        elif parsed_command.command_type == CommandType.TASK:
            # Handle task creation
            try:
                from app.application.use_cases.task_use_cases import TaskUseCases
                task_use_cases = TaskUseCases(self.db)

                # Get parameters from command parser
                params = parsed_command.parameters
                title = params.get("title") or parsed_command.command_text

                if not title or len(title.strip()) == 0:
                    return "❌ Taak titel kan niet leeg zijn.\n\nVoorbeeld: #task Rapport maken deadline volgende week @Maria"

                # Create task
                task = task_use_cases.create_task(
                    user_id=conversation.user_id,
                    title=title,
                    delegated_to_name=params.get("delegated_to"),
                    due_date=params.get("due_date"),
                    priority=params.get("priority", "medium"),
                    tags=params.get("tags", []),
                )

                # Build response message
                response_lines = [
                    f"✅ Taak aangemaakt!",
                    f"",
                    f"**{task['formatted_id']}**: {task['title']}",
                ]

                if task.get("delegated_person_name"):
                    response_lines.append(f"👤 Gedelegeerd aan: {task['delegated_person_name']}")

                if task.get("due_date"):
                    response_lines.append(f"📅 Deadline: {task['due_date']}")

                response_lines.append(f"⚡ Prioriteit: {task['priority']}")

                if task.get("tags"):
                    response_lines.append(f"🏷️  Tags: {', '.join(task['tags'])}")

                return "\n".join(response_lines)

            except Exception as e:
                return f"❌ Kon de taak niet maken: {str(e)}"

        elif parsed_command.command_type == CommandType.NOTE:
            return "📝 Notitie functie wordt geactiveerd. Wat wil je noteren?\n\n" + parsed_command.get_help_text()

        elif parsed_command.command_type == CommandType.SCAN:
            return "📸 Scan functie wordt geactiveerd. Upload een document om te scannen.\n\n" + parsed_command.get_help_text()

        else:
            return f"Onbekend commando. Typ #help voor beschikbare commando's."

    async def _get_ai_response(self, conversation: Conversation, mode: str) -> str:
        """Get AI response for conversation."""
        # Get recent messages for context
        messages = conversation.get_messages_for_claude(max_messages=50)

        # Get system prompt for mode
        system_prompt = self.claude_service.get_system_prompt(mode)

        # Call Claude API
        response = await self.claude_service.send_message(
            messages=messages,
            system_prompt=system_prompt,
        )

        # Extract text from response
        content_blocks = response.get("content", [])
        text_parts = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]

        return "".join(text_parts)

    async def _get_ai_response_stream(self, conversation: Conversation, mode: str) -> AsyncIterator[str]:
        """Stream AI response for conversation with tool use support."""
        # Get recent messages for context
        messages = conversation.get_messages_for_claude(max_messages=50)

        # Get system prompt for mode
        system_prompt = self.claude_service.get_system_prompt(mode)

        # Get calendar tools
        tools = self.claude_service.get_calendar_tools()

        # Add current date/time to system prompt for better date parsing
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        # Use Amsterdam/Europe timezone
        tz_nl = ZoneInfo("Europe/Amsterdam")
        now = datetime.now(tz_nl)

        # Create a week view for better date parsing
        days_nl = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']
        week_info = []
        for i in range(7):
            day = now + timedelta(days=i)
            day_name = days_nl[day.weekday()]
            label = "VANDAAG" if i == 0 else "MORGEN" if i == 1 else ""
            week_info.append(f"  - {day_name.capitalize()} {day.strftime('%d-%m-%Y')} {label}")

        week_view = "\n".join(week_info)

        # Calculate next occurrence of each weekday
        def next_weekday(target_weekday: int) -> str:
            days_ahead = target_weekday - now.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).strftime('%d-%m-%Y')

        enhanced_system_prompt = f"""{system_prompt}

HUIDIGE DATUM EN TIJD CONTEXT:
Vandaag is {days_nl[now.weekday()]} {now.strftime('%d-%m-%Y')} om {now.strftime('%H:%M')}

Komende week (voor datum referentie):
{week_view}

KRITIEKE REGELS VOOR DATUM PARSING:
1. GEBRUIK ALTIJD de exacte datums uit de lijst hierboven
2. Als de gebruiker een weekdag noemt (bijv. "donderdag"), zoek die dag in de lijst hierboven en gebruik DIE datum
3. "morgen" = {(now + timedelta(days=1)).strftime('%d-%m-%Y')} ({days_nl[(now + timedelta(days=1)).weekday()]})
4. "overmorgen" = {(now + timedelta(days=2)).strftime('%d-%m-%Y')} ({days_nl[(now + timedelta(days=2)).weekday()]})
5. NOOIT een datum gokken - gebruik ALLEEN de datums uit de context hierboven
6. Bij twijfel: VRAAG om bevestiging voordat je de tool aanroept

KRITIEKE REGELS VOOR PROVIDER SELECTIE:
1. Als de gebruiker "google", "Google Calendar" of "gcal" noemt → gebruik provider: "google"
2. Als de gebruiker "microsoft", "outlook", "o365" of "Office 365" noemt → gebruik provider: "microsoft"
3. Als de gebruiker GEEN provider noemt → LAAT provider LEEG (dan wordt de primary calendar gebruikt)
4. Let op: de gebruiker kan zeggen "zet in mijn google agenda" of "in outlook" - detecteer dit!
"""

        # Stream from Claude API
        tool_uses = []  # Collect tool uses during streaming
        text_response = ""

        async for event in self.claude_service.send_message_stream(
            messages=messages,
            system_prompt=enhanced_system_prompt,
            tools=tools,
        ):
            if event["type"] == "text":
                # Regular text response
                text_response += event["text"]
                yield event["text"]

            elif event["type"] == "tool_use":
                # Claude wants to use a tool
                tool_uses.append(event)

        # After streaming completes, execute any tool uses
        if tool_uses:
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]

                try:
                    if tool_name == "create_calendar_event":
                        # Execute calendar event creation
                        result = await self._execute_create_calendar_event(
                            conversation.user_id,
                            tool_input
                        )
                        # Yield the result message
                        yield f"\n\n{result}"

                    elif tool_name == "create_reminder":
                        # Execute reminder creation
                        result = await self._execute_create_reminder(
                            conversation.user_id,
                            tool_input
                        )
                        # Yield the result message
                        yield f"\n\n{result}"

                except Exception as e:
                    error_msg = f"\n\n❌ Fout bij uitvoeren actie: {str(e)}"
                    yield error_msg

    async def _execute_create_calendar_event(self, user_id: UUID, tool_input: dict, original_input: str = "") -> str:
        """Execute calendar event creation via MCP Distributor."""
        from app.infrastructure.services.mcp_distributor import MCPDistributor, InputSource
        from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository
        from app.core.test_mode_context import get_test_mode
        import json

        try:
            # Get user's primary calendar provider
            settings_repo = UserSettingsRepository(self.db)
            settings = settings_repo.get_settings(user_id)
            primary_provider = settings.primary_calendar_provider if settings else "microsoft"

            # Create distributor
            distributor = MCPDistributor(primary_provider=primary_provider)

            # Execute via MCP Distributor (test_mode read from context automatically)
            result = await distributor.route_and_execute(
                tool_name="create_calendar_event",
                tool_params=tool_input,
                user_id=str(user_id),
                input_source=InputSource.CHAT,
                original_input=original_input,
                provider=tool_input.get("provider"),
            )

            # Get test_mode from context to format response
            test_mode = get_test_mode()

            # Handle test mode responses
            if test_mode == 1:
                trace = result.route_trace
                if trace:
                    return f"🔧 **TEST MODE: Alleen logging**\n\n" \
                           f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                           f"🔧 Tool: {trace.tool_name}\n" \
                           f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                           f"⚠️ Geen uitvoering (test_mode=1)"
                return "🔧 Test mode: geen uitvoering"

            if test_mode == 2 and result.requires_confirmation:
                trace = result.route_trace
                if trace:
                    return f"🔧 **TEST MODE: Bevestiging vereist**\n\n" \
                           f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                           f"🔧 Tool: {trace.tool_name}\n" \
                           f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                           f"⏳ Wacht op bevestiging via popup..."
                return "🔧 Wacht op bevestiging..."

            # Normal execution result
            if result.success and result.data:
                provider_name = "Google Calendar" if tool_input.get("provider") == "google" else "Office 365"
                return f"✅ Agenda-afspraak aangemaakt!\n\n📅 **{tool_input['title']}**\n🕐 {tool_input['start_time']} - {tool_input['end_time']}\n📍 {tool_input.get('location') or 'Geen locatie'}\n\nDe afspraak is toegevoegd aan je {provider_name}."
            else:
                return f"❌ Kon de afspraak niet maken: {result.error}"

        except Exception as e:
            return f"❌ Kon de afspraak niet maken: {str(e)}\n\nZorg dat je een kalender hebt gekoppeld in Settings."

    async def _execute_create_reminder(self, user_id: UUID, tool_input: dict, original_input: str = "") -> str:
        """Execute reminder creation via MCP Distributor."""
        from app.infrastructure.services.mcp_distributor import MCPDistributor, InputSource
        from app.infrastructure.repositories.user_settings_repository import UserSettingsRepository
        from app.core.test_mode_context import get_test_mode
        import json

        try:
            # Get user's primary calendar provider
            settings_repo = UserSettingsRepository(self.db)
            settings = settings_repo.get_settings(user_id)
            primary_provider = settings.primary_calendar_provider if settings else "microsoft"

            # Create distributor
            distributor = MCPDistributor(primary_provider=primary_provider)

            # Execute via MCP Distributor (test_mode read from context automatically)
            result = await distributor.route_and_execute(
                tool_name="create_reminder",
                tool_params=tool_input,
                user_id=str(user_id),
                input_source=InputSource.CHAT,
                original_input=original_input,
                provider=tool_input.get("provider"),
            )

            # Get test_mode from context to format response
            test_mode = get_test_mode()

            # Handle test mode responses
            if test_mode == 1:
                trace = result.route_trace
                if trace:
                    return f"🔧 **TEST MODE: Alleen logging**\n\n" \
                           f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                           f"🔧 Tool: {trace.tool_name}\n" \
                           f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                           f"⚠️ Geen uitvoering (test_mode=1)"
                return "🔧 Test mode: geen uitvoering"

            if test_mode == 2 and result.requires_confirmation:
                trace = result.route_trace
                if trace:
                    return f"🔧 **TEST MODE: Bevestiging vereist**\n\n" \
                           f"📍 Route: {trace.input_source} → {trace.detected_intent} → {trace.selected_mcp}\n" \
                           f"🔧 Tool: {trace.tool_name}\n" \
                           f"📋 Parameters:\n```json\n{json.dumps(trace.tool_params, indent=2, ensure_ascii=False)}\n```\n\n" \
                           f"⏳ Wacht op bevestiging via popup..."
                return "🔧 Wacht op bevestiging..."

            # Normal execution result
            if result.success and result.data:
                provider_name = "Google Calendar" if tool_input.get("provider") == "google" else "Office 365"
                return f"⏰ Herinnering aangemaakt!\n\n📝 {tool_input['title']}\n🕐 {tool_input['reminder_time']}\n\nDe herinnering is toegevoegd aan je {provider_name}."
            else:
                return f"❌ Kon de herinnering niet maken: {result.error}"

        except Exception as e:
            return f"❌ Kon de herinnering niet maken: {str(e)}\n\nZorg dat je een kalender hebt gekoppeld in Settings."

    def get_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)
            limit: Max messages
            offset: Offset for pagination

        Returns:
            List of Message entities
        """
        # Verify access
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        message_models = self.conversation_repo.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )

        return [
            Message(
                id=str(msg.id),
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.metadata or {},
            )
            for msg in message_models
        ]

    def delete_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted

        Raises:
            ValueError: If conversation not found or access denied
        """
        # Verify access
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        return self.conversation_repo.delete_conversation(conversation_id)

    async def generate_title(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> str:
        """
        Generate an AI-powered title for a conversation.

        Uses Claude to summarize the conversation into a short, descriptive title.
        Similar to Claude Desktop's automatic title generation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)

        Returns:
            Generated title string (2-5 words)

        Raises:
            ValueError: If conversation not found or access denied
        """
        # Get conversation
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # If no messages, return default
        if not conversation.messages or len(conversation.messages) == 0:
            return "Nieuwe chat"

        # Get first few messages for context (max 5 messages or 500 chars)
        messages_context = []
        total_chars = 0
        for msg in conversation.messages[:5]:
            if total_chars > 500:
                break
            messages_context.append(f"{msg.role}: {msg.content}")
            total_chars += len(msg.content)

        context = "\n".join(messages_context)

        # Ask Claude to generate a short title
        prompt = f"""Geef een korte, beschrijvende titel (2-5 woorden) voor dit gesprek:

{context}

Regels:
- Maximaal 5 woorden
- Beschrijf het hoofdonderwerp
- In het Nederlands
- Geen aanhalingstekens of speciale tekens
- Gewoon de titel, niets anders

Titel:"""

        try:
            response = await self.claude_service.send_message(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Je bent een expert in het maken van korte, beschrijvende titels. Geef alleen de titel, niets anders.",
                max_tokens=50,
                temperature=0.7,
            )

            # Extract title from response
            title = response["content"][0]["text"].strip()

            # Remove quotes if present
            title = title.strip('"').strip("'")

            # Limit to 50 chars
            if len(title) > 50:
                title = title[:50].strip()

            # Update conversation title
            self.conversation_repo.update_conversation(conversation_id, title=title)

            return title

        except Exception as e:
            # Fallback to first message preview if AI generation fails
            first_user_msg = next((msg for msg in conversation.messages if msg.role == "user"), None)
            if first_user_msg:
                fallback = first_user_msg.content[:30].strip()
                if len(first_user_msg.content) > 30:
                    fallback += "..."
                return fallback
            return "Nieuwe chat"
