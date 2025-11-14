"""
Conversation use cases.
Part of Application layer - orchestrates conversation operations.
"""
from typing import Optional, List, AsyncIterator
from uuid import UUID
from sqlalchemy.orm import Session

from app.domain.entities.conversation import Conversation, Message
from app.domain.services.command_parser import CommandParser, CommandType
from app.infrastructure.repositories.conversation_repository import ConversationRepository
from app.infrastructure.services.claude_service import ClaudeService


class ConversationUseCases:
    """
    Use cases for conversation management and AI chat.
    """

    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.claude_service = ClaudeService()
        self.command_parser = CommandParser()

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

        # Handle special commands
        if parsed_command.is_command():
            response_content = await self._handle_command(parsed_command, conversation)
        else:
            # Get AI response
            response_content = await self._get_ai_response(conversation, mode or conversation.mode)

        # Save assistant response
        assistant_message = self.conversation_repo.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_content,
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
    ) -> AsyncIterator[str]:
        """
        Send a message and stream AI response.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            content: Message content
            mode: Optional conversation mode override

        Yields:
            Text chunks from AI response

        Raises:
            ValueError: If conversation not found
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

        # Handle commands or get AI response
        if parsed_command.is_command():
            response_content = await self._handle_command(parsed_command, conversation)
            # Save response
            self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_content,
            )
            yield response_content
        else:
            # Stream AI response
            full_response = ""
            async for chunk in self._get_ai_response_stream(conversation, mode or conversation.mode):
                full_response += chunk
                yield chunk

            # Save complete response
            self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
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
            return "📅 Calendar functie wordt geactiveerd. Wat wil je met je agenda doen?\n\n" + parsed_command.get_help_text()

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
        """Stream AI response for conversation."""
        # Get recent messages for context
        messages = conversation.get_messages_for_claude(max_messages=50)

        # Get system prompt for mode
        system_prompt = self.claude_service.get_system_prompt(mode)

        # Stream from Claude API
        async for chunk in self.claude_service.send_message_stream(
            messages=messages,
            system_prompt=system_prompt,
        ):
            yield chunk

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
