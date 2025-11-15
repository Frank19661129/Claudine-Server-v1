"""
InboxItem use cases.
Part of Application layer - orchestrates inbox processing with AI.
"""
import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.entities.inbox_item import InboxItem, InboxItemType, InboxStatus, Priority
from app.infrastructure.repositories.inbox_repository import InboxRepository
from app.infrastructure.repositories.task_repository import TaskRepository
from app.infrastructure.repositories.note_repository import NoteRepository
from app.infrastructure.services.claude_service import ClaudeService


class InboxUseCases:
    """
    Use cases for inbox item processing with AI assistance.
    Handles inbox item lifecycle from creation to processing.
    """

    def __init__(self, db: Session):
        self.db = db
        self.inbox_repo = InboxRepository(db)
        self.task_repo = TaskRepository(db)
        self.note_repo = NoteRepository(db)
        self.claude_service = ClaudeService()

    def create_inbox_item(
        self,
        user_id: UUID,
        type: InboxItemType,
        source: str,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.MEDIUM,
    ) -> dict:
        """
        Create a new inbox item.

        Args:
            user_id: User ID
            type: Type of inbox item
            source: Source of the item
            subject: Subject/title
            content: Main content
            raw_data: Raw data from source
            priority: Priority level

        Returns:
            Inbox item dict
        """
        # Use domain entity for validation
        item_entity = InboxItem.create(
            user_id=user_id,
            type=type,
            source=source,
            subject=subject,
            content=content,
            raw_data=raw_data,
            priority=priority,
        )

        # Create in database
        item_model = self.inbox_repo.create_inbox_item(
            user_id=user_id,
            type=item_entity.type,
            source=item_entity.source,
            status=item_entity.status,
            priority=item_entity.priority,
            subject=item_entity.subject,
            content=item_entity.content,
            raw_data=item_entity.raw_data,
        )

        return self._model_to_dict(item_model)

    def get_inbox_item(self, item_id: UUID, user_id: UUID) -> Optional[dict]:
        """Get a single inbox item."""
        item_model = self.inbox_repo.get_inbox_item(item_id, user_id)
        if not item_model:
            return None
        return self._model_to_dict(item_model)

    def get_inbox_items(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get inbox items with filters."""
        items, total = self.inbox_repo.get_user_inbox_items(
            user_id=user_id,
            status=status,
            type=type,
            priority=priority,
            skip=skip,
            limit=limit,
        )

        return {
            "items": [self._model_to_dict(item) for item in items],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_unprocessed_count(self, user_id: UUID) -> int:
        """Get count of unprocessed items."""
        return self.inbox_repo.get_unprocessed_count(user_id)

    async def request_ai_suggestion(
        self, item_id: UUID, user_id: UUID
    ) -> Optional[dict]:
        """
        Request AI suggestion for processing an inbox item.

        Args:
            item_id: Inbox item ID
            user_id: User ID

        Returns:
            Updated inbox item with AI suggestion
        """
        item_model = self.inbox_repo.get_inbox_item(item_id, user_id)
        if not item_model:
            return None

        # Build prompt for Claude
        system_prompt = """Je bent Claudine, een Nederlandse persoonlijke assistent.
Je helpt met het verwerken van inbox items door suggesties te doen.

Analyseer het inbox item en bepaal de beste actie:
- create_task: Als het een actiepunt is dat gedaan moet worden
- create_note: Als het informatie is die bewaard moet worden
- create_event: Als het een afspraak of gebeurtenis is (niet geïmplementeerd)
- delegate: Als het gedelegeerd moet worden aan iemand anders
- archive: Als het geen actie vereist

Geef je antwoord in JSON format met deze velden:
{
  "action": "create_task|create_note|archive|delegate",
  "confidence": 0.0-1.0,
  "reasoning": "waarom je deze actie voorstelt",
  "suggested_data": {
    "title": "...",
    "content": "...",
    "priority": "low|medium|high|urgent",
    "tags": ["tag1", "tag2"],
    ... (andere relevante velden)
  },
  "alternative_actions": [
    {"action": "...", "reasoning": "..."}
  ]
}
"""

        # Prepare item content for analysis
        item_content = f"""Type: {item_model.type}
Bron: {item_model.source}
Onderwerp: {item_model.subject or 'Geen onderwerp'}

Inhoud:
{item_model.content or 'Geen inhoud'}
"""

        messages = [{"role": "user", "content": item_content}]

        try:
            # Get AI suggestion
            response = await self.claude_service.send_message(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.3,  # Lower temperature for more deterministic output
            )

            # Extract suggestion from response
            content_text = response["content"][0]["text"]

            # Try to parse JSON from response
            try:
                # Sometimes Claude wraps JSON in markdown code blocks
                if "```json" in content_text:
                    json_start = content_text.find("```json") + 7
                    json_end = content_text.find("```", json_start)
                    content_text = content_text[json_start:json_end].strip()
                elif "```" in content_text:
                    json_start = content_text.find("```") + 3
                    json_end = content_text.find("```", json_start)
                    content_text = content_text[json_start:json_end].strip()

                suggestion = json.loads(content_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, create a default suggestion
                suggestion = {
                    "action": "archive",
                    "confidence": 0.5,
                    "reasoning": "Kon geen duidelijke actie bepalen",
                    "suggested_data": {},
                    "alternative_actions": [],
                }

            # Update item with AI suggestion
            updated_item = self.inbox_repo.update_inbox_item(
                item_id=item_id,
                user_id=user_id,
                ai_suggestion=suggestion,
                status=InboxStatus.PENDING_REVIEW,
            )

            if not updated_item:
                return None

            return self._model_to_dict(updated_item)

        except Exception as e:
            # Log error and return item without suggestion
            print(f"Error getting AI suggestion: {e}")
            return self._model_to_dict(item_model)

    async def accept_suggestion(
        self, item_id: UUID, user_id: UUID
    ) -> Optional[dict]:
        """
        Accept AI suggestion and execute the action.

        Args:
            item_id: Inbox item ID
            user_id: User ID

        Returns:
            Result with created item info
        """
        item_model = self.inbox_repo.get_inbox_item(item_id, user_id)
        if not item_model or not item_model.ai_suggestion:
            return None

        suggestion = item_model.ai_suggestion
        action = suggestion.get("action")
        suggested_data = suggestion.get("suggested_data", {})

        created_item = None

        # Execute action based on suggestion
        if action == "create_task":
            # Create task from suggestion
            task_model = self.task_repo.create_task(
                user_id=user_id,
                title=suggested_data.get("title", item_model.subject or "Nieuwe taak"),
                memo=suggested_data.get("content", item_model.content),
                priority=suggested_data.get("priority", "medium"),
                tags=suggested_data.get("tags", []),
                due_date=suggested_data.get("due_date"),
            )
            created_item = {
                "type": "task",
                "id": str(task_model.id),
                "task_number": task_model.task_number,
            }

        elif action == "create_note":
            # Create note from suggestion
            note_model = self.note_repo.create_note(
                user_id=user_id,
                title=suggested_data.get("title", item_model.subject),
                content=suggested_data.get("content", item_model.content),
                categories=suggested_data.get("tags", []),
                color=suggested_data.get("color", "yellow"),
            )
            created_item = {
                "type": "note",
                "id": str(note_model.id),
            }

        elif action == "archive":
            # Just mark as archived
            pass

        # Update inbox item status
        updated_item = self.inbox_repo.update_inbox_item(
            item_id=item_id,
            user_id=user_id,
            status=InboxStatus.ACCEPTED,
            processed_at=datetime.utcnow(),
            user_decision={"action": "accepted", "timestamp": datetime.utcnow().isoformat()},
            linked_items=[created_item] if created_item else [],
        )

        return {
            "inbox_item": self._model_to_dict(updated_item),
            "created_item": created_item,
        }

    def modify_and_accept(
        self,
        item_id: UUID,
        user_id: UUID,
        modifications: Dict[str, Any],
    ) -> Optional[dict]:
        """
        Accept with modifications and execute action.

        Args:
            item_id: Inbox item ID
            user_id: User ID
            modifications: Modified suggestion data

        Returns:
            Result with created item info
        """
        item_model = self.inbox_repo.get_inbox_item(item_id, user_id)
        if not item_model:
            return None

        action = modifications.get("action")
        data = modifications.get("data", {})

        created_item = None

        # Execute action based on modifications
        if action == "create_task":
            task_model = self.task_repo.create_task(
                user_id=user_id,
                title=data.get("title", item_model.subject or "Nieuwe taak"),
                memo=data.get("content", item_model.content),
                priority=data.get("priority", "medium"),
                tags=data.get("tags", []),
                due_date=data.get("due_date"),
            )
            created_item = {
                "type": "task",
                "id": str(task_model.id),
                "task_number": task_model.task_number,
            }

        elif action == "create_note":
            note_model = self.note_repo.create_note(
                user_id=user_id,
                title=data.get("title", item_model.subject),
                content=data.get("content", item_model.content),
                categories=data.get("tags", []),
                color=data.get("color", "yellow"),
            )
            created_item = {
                "type": "note",
                "id": str(note_model.id),
            }

        # Update inbox item
        updated_item = self.inbox_repo.update_inbox_item(
            item_id=item_id,
            user_id=user_id,
            status=InboxStatus.MODIFIED,
            processed_at=datetime.utcnow(),
            user_decision={
                "action": "modified",
                "modifications": modifications,
                "timestamp": datetime.utcnow().isoformat(),
            },
            linked_items=[created_item] if created_item else [],
        )

        return {
            "inbox_item": self._model_to_dict(updated_item),
            "created_item": created_item,
        }

    def reject_item(
        self, item_id: UUID, user_id: UUID, reason: Optional[str] = None
    ) -> Optional[dict]:
        """Reject an inbox item."""
        updated_item = self.inbox_repo.update_inbox_item(
            item_id=item_id,
            user_id=user_id,
            status=InboxStatus.REJECTED,
            processed_at=datetime.utcnow(),
            user_decision={
                "action": "rejected",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        if not updated_item:
            return None

        return self._model_to_dict(updated_item)

    def archive_item(self, item_id: UUID, user_id: UUID) -> Optional[dict]:
        """Archive an inbox item without processing."""
        updated_item = self.inbox_repo.update_inbox_item(
            item_id=item_id,
            user_id=user_id,
            status=InboxStatus.ARCHIVED,
            processed_at=datetime.utcnow(),
        )

        if not updated_item:
            return None

        return self._model_to_dict(updated_item)

    def delete_item(self, item_id: UUID, user_id: UUID) -> bool:
        """Delete an inbox item."""
        return self.inbox_repo.delete_inbox_item(item_id, user_id)

    def _model_to_dict(self, model) -> dict:
        """Convert database model to dict for API response."""
        return {
            "id": str(model.id),
            "user_id": str(model.user_id),
            "type": model.type,
            "source": model.source,
            "status": model.status,
            "priority": model.priority,
            "subject": model.subject,
            "content": model.content,
            "raw_data": model.raw_data or {},
            "ai_suggestion": model.ai_suggestion,
            "user_decision": model.user_decision,
            "linked_items": model.linked_items or [],
            "processed_at": model.processed_at.isoformat() if model.processed_at else None,
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
        }
