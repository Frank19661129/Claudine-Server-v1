"""
Conversation domain entity.
Part of Domain layer - contains business logic and rules.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class Message:
    """
    Single message in a conversation.
    """
    id: Optional[str]
    conversation_id: Optional[UUID]
    role: str  # user, assistant, system
    content: str
    created_at: datetime
    metadata: Optional[dict] = None  # For storing extra info (commands, attachments, etc.)

    def is_user_message(self) -> bool:
        """Check if message is from user."""
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if message is from assistant."""
        return self.role == "assistant"

    def has_command(self) -> bool:
        """Check if message contains a command keyword."""
        return self.content.strip().startswith("#")

    def extract_command(self) -> Optional[str]:
        """Extract command from message (e.g., #calendar → calendar)."""
        if not self.has_command():
            return None

        first_word = self.content.strip().split()[0]
        return first_word[1:].lower()  # Remove # and lowercase


@dataclass
class Conversation:
    """
    Conversation domain entity.
    Represents a chat session between user and Claude.
    """
    id: Optional[UUID]
    user_id: UUID
    title: str
    mode: str  # chat, voice, note, scan
    created_at: datetime
    updated_at: datetime
    messages: List[Message] = field(default_factory=list)
    metadata: Optional[dict] = None

    @classmethod
    def create(
        cls,
        user_id: UUID,
        mode: str = "chat",
        title: Optional[str] = None,
    ) -> "Conversation":
        """
        Factory method to create a new conversation.
        Enforces business rules at creation time.
        """
        # Validate mode
        valid_modes = ["chat", "voice", "note", "scan"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        # Auto-generate title if not provided
        if not title:
            now = datetime.utcnow()
            title = f"{mode.capitalize()} conversation - {now.strftime('%Y-%m-%d %H:%M')}"

        now = datetime.utcnow()
        return cls(
            id=None,  # Will be set by repository
            user_id=user_id,
            title=title.strip(),
            mode=mode,
            created_at=now,
            updated_at=now,
            messages=[],
            metadata={},
        )

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Add a message to the conversation.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata

        Returns:
            Created message
        """
        if role not in ["user", "assistant", "system"]:
            raise ValueError(f"Invalid role: {role}")

        if not content or len(content.strip()) == 0:
            raise ValueError("Message content cannot be empty")

        message = Message(
            id=None,
            conversation_id=self.id,
            role=role,
            content=content.strip(),
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )

        self.messages.append(message)
        self.updated_at = datetime.utcnow()

        return message

    def get_messages_for_claude(self, max_messages: int = 50) -> List[dict]:
        """
        Get messages in Claude API format.

        Args:
            max_messages: Maximum number of messages to include

        Returns:
            List of messages in Claude format [{"role": "user", "content": "..."}]
        """
        # Get last N messages (excluding system messages for now)
        recent_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages[-max_messages:]
            if msg.role in ["user", "assistant"]
        ]

        return recent_messages

    def get_latest_user_message(self) -> Optional[Message]:
        """Get the most recent user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

    def message_count(self) -> int:
        """Get total number of messages in conversation."""
        return len(self.messages)

    def update_title(self, new_title: str):
        """Update conversation title."""
        if not new_title or len(new_title.strip()) == 0:
            raise ValueError("Title cannot be empty")

        self.title = new_title.strip()
        self.updated_at = datetime.utcnow()
