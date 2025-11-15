"""
InboxItem repository implementation.
Part of Infrastructure layer - handles database operations.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.infrastructure.database.models import InboxItemModel
from app.domain.entities.inbox_item import InboxItem, InboxItemType, InboxStatus, Priority


class InboxRepository:
    """Repository for InboxItem persistence."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def create_inbox_item(
        self,
        user_id: UUID,
        type: InboxItemType,
        source: str,
        status: InboxStatus,
        priority: Priority,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        ai_suggestion: Optional[Dict[str, Any]] = None,
        user_decision: Optional[Dict[str, Any]] = None,
        linked_items: Optional[List[Dict[str, Any]]] = None,
        processed_at: Optional[datetime] = None,
    ) -> InboxItemModel:
        """Create a new inbox item."""
        item = InboxItemModel(
            user_id=user_id,
            type=type.value,
            source=source,
            status=status.value,
            priority=priority.value,
            subject=subject,
            content=content,
            raw_data=raw_data or {},
            ai_suggestion=ai_suggestion,
            user_decision=user_decision,
            linked_items=linked_items or [],
            processed_at=processed_at,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_inbox_item(self, item_id: UUID, user_id: UUID) -> Optional[InboxItemModel]:
        """Get a single inbox item by ID."""
        return (
            self.db.query(InboxItemModel)
            .filter(
                and_(
                    InboxItemModel.id == item_id,
                    InboxItemModel.user_id == user_id,
                )
            )
            .first()
        )

    def get_user_inbox_items(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[InboxItemModel], int]:
        """Get inbox items for a user with optional filters."""
        query = self.db.query(InboxItemModel).filter(
            InboxItemModel.user_id == user_id
        )

        # Apply filters
        if status:
            # Support multiple statuses separated by comma
            statuses = [s.strip() for s in status.split(",")]
            query = query.filter(InboxItemModel.status.in_(statuses))

        if type:
            # Support multiple types separated by comma
            types = [t.strip() for t in type.split(",")]
            query = query.filter(InboxItemModel.type.in_(types))

        if priority:
            # Support multiple priorities separated by comma
            priorities = [p.strip() for p in priority.split(",")]
            query = query.filter(InboxItemModel.priority.in_(priorities))

        # Get total count before pagination
        total = query.count()

        # Apply sorting and pagination
        items = (
            query.order_by(InboxItemModel.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total

    def update_inbox_item(
        self,
        item_id: UUID,
        user_id: UUID,
        **updates,
    ) -> Optional[InboxItemModel]:
        """Update an inbox item."""
        item = self.get_inbox_item(item_id, user_id)
        if not item:
            return None

        # Update allowed fields
        allowed_fields = {
            "status",
            "priority",
            "subject",
            "content",
            "raw_data",
            "ai_suggestion",
            "user_decision",
            "linked_items",
            "processed_at",
        }

        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                # Convert enums to values if needed
                if hasattr(value, "value"):
                    value = value.value
                setattr(item, key, value)

        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_inbox_item(self, item_id: UUID, user_id: UUID) -> bool:
        """Delete an inbox item."""
        item = self.get_inbox_item(item_id, user_id)
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()
        return True

    def get_unprocessed_count(self, user_id: UUID) -> int:
        """Get count of unprocessed items for a user."""
        return (
            self.db.query(InboxItemModel)
            .filter(
                and_(
                    InboxItemModel.user_id == user_id,
                    InboxItemModel.status == InboxStatus.UNPROCESSED.value,
                )
            )
            .count()
        )

    def _model_to_entity(self, model: InboxItemModel) -> InboxItem:
        """Convert database model to domain entity."""
        return InboxItem(
            id=model.id,
            user_id=model.user_id,
            type=InboxItemType(model.type),
            source=model.source,
            status=InboxStatus(model.status),
            priority=Priority(model.priority),
            subject=model.subject,
            content=model.content,
            raw_data=model.raw_data or {},
            ai_suggestion=model.ai_suggestion,
            user_decision=model.user_decision,
            linked_items=model.linked_items or [],
            processed_at=model.processed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _entity_to_dict(self, entity: InboxItem) -> dict:
        """Convert entity to dictionary for API response."""
        return {
            "id": str(entity.id) if entity.id else None,
            "user_id": str(entity.user_id),
            "type": entity.type.value,
            "source": entity.source,
            "status": entity.status.value,
            "priority": entity.priority.value,
            "subject": entity.subject,
            "content": entity.content,
            "raw_data": entity.raw_data,
            "ai_suggestion": entity.ai_suggestion,
            "user_decision": entity.user_decision,
            "linked_items": entity.linked_items,
            "processed_at": entity.processed_at.isoformat() if entity.processed_at else None,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
