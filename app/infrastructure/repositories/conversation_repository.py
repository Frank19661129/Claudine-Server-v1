"""
Conversation repository - data access layer.
Part of Infrastructure layer.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.infrastructure.database.models import ConversationModel, MessageModel
from app.domain.entities.conversation import Conversation, Message


class ConversationRepository:
    """Repository for conversation persistence operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_conversation(
        self,
        user_id: UUID,
        title: str,
        mode: str = "chat",
        metadata: Optional[dict] = None,
    ) -> ConversationModel:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            title: Conversation title
            mode: Conversation mode (chat, voice, note, scan)
            metadata: Optional metadata

        Returns:
            Created ConversationModel
        """
        conversation = ConversationModel(
            user_id=user_id,
            title=title,
            mode=mode,
            meta=metadata or {},
        )

        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    def get_conversation(
        self,
        conversation_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[ConversationModel]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation ID
            user_id: Optional user ID to verify ownership

        Returns:
            ConversationModel or None
        """
        query = self.db.query(ConversationModel).filter(
            ConversationModel.id == conversation_id
        )

        if user_id:
            query = query.filter(ConversationModel.user_id == user_id)

        return query.first()

    def get_user_conversations(
        self,
        user_id: UUID,
        mode: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConversationModel]:
        """
        Get all conversations for a user.

        Args:
            user_id: User ID
            mode: Optional filter by mode
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of ConversationModel
        """
        query = self.db.query(ConversationModel).filter(
            ConversationModel.user_id == user_id
        )

        if mode:
            query = query.filter(ConversationModel.mode == mode)

        query = query.order_by(desc(ConversationModel.updated_at))
        query = query.limit(limit).offset(offset)

        return query.all()

    def update_conversation(
        self,
        conversation_id: UUID,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[ConversationModel]:
        """
        Update a conversation.

        Args:
            conversation_id: Conversation ID
            title: New title
            metadata: New metadata

        Returns:
            Updated ConversationModel or None
        """
        conversation = self.db.query(ConversationModel).filter(
            ConversationModel.id == conversation_id
        ).first()

        if not conversation:
            return None

        if title is not None:
            conversation.title = title

        if metadata is not None:
            conversation.meta = metadata

        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    def delete_conversation(self, conversation_id: UUID) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if deleted, False if not found
        """
        conversation = self.db.query(ConversationModel).filter(
            ConversationModel.id == conversation_id
        ).first()

        if not conversation:
            return False

        self.db.delete(conversation)
        self.db.commit()

        return True

    def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> MessageModel:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata

        Returns:
            Created MessageModel
        """
        message = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            meta=metadata or {},
        )

        self.db.add(message)

        # Update conversation updated_at timestamp
        conversation = self.db.query(ConversationModel).filter(
            ConversationModel.id == conversation_id
        ).first()

        if conversation:
            from datetime import datetime
            conversation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)

        return message

    def get_messages(
        self,
        conversation_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MessageModel]:
        """
        Get messages for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages
            offset: Offset for pagination

        Returns:
            List of MessageModel ordered by created_at
        """
        messages = self.db.query(MessageModel).filter(
            MessageModel.conversation_id == conversation_id
        ).order_by(MessageModel.created_at).limit(limit).offset(offset).all()

        return messages

    def get_latest_messages(
        self,
        conversation_id: UUID,
        limit: int = 50,
    ) -> List[MessageModel]:
        """
        Get the most recent messages from a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Number of recent messages

        Returns:
            List of MessageModel (ordered oldest to newest)
        """
        messages = self.db.query(MessageModel).filter(
            MessageModel.conversation_id == conversation_id
        ).order_by(desc(MessageModel.created_at)).limit(limit).all()

        # Reverse to get chronological order (oldest first)
        return list(reversed(messages))

    def conversation_to_entity(self, model: ConversationModel) -> Conversation:
        """
        Convert ConversationModel to domain entity.

        Args:
            model: ConversationModel from database

        Returns:
            Conversation domain entity
        """
        messages = [
            Message(
                id=str(msg.id),
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.meta or {},
            )
            for msg in model.messages
        ]

        return Conversation(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            mode=model.mode,
            created_at=model.created_at,
            updated_at=model.updated_at,
            messages=messages,
            metadata=model.meta or {},
        )
