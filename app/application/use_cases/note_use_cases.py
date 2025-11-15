"""
Note use cases.
Part of Application layer - orchestrates note management operations.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.entities.note import Note, NoteItem
from app.domain.entities.note_group import NoteGroup
from app.infrastructure.repositories.note_repository import NoteRepository


class NoteUseCases:
    """
    Use cases for note management operations.
    Handles CRUD operations for notes, note groups, and checklist items.
    """

    def __init__(self, db: Session):
        self.db = db
        self.note_repo = NoteRepository(db)

    # ==================== Note Group Use Cases ====================

    def create_note_group(
        self,
        user_id: UUID,
        name: str,
        color: str = "blue",
        icon: Optional[str] = None,
        sort_order: int = 0,
    ) -> dict:
        """Create a new note group."""
        # Use domain entity for validation
        group_entity = NoteGroup.create(
            user_id=user_id,
            name=name,
            color=color,
            icon=icon,
            sort_order=sort_order,
        )

        # Create in database
        group_model = self.note_repo.create_note_group(
            user_id=user_id,
            name=group_entity.name,
            color=group_entity.color,
            icon=group_entity.icon,
            sort_order=group_entity.sort_order,
        )

        return self._group_model_to_dict(group_model)

    def get_note_group(self, group_id: UUID, user_id: UUID) -> Optional[dict]:
        """Get a note group by ID."""
        group_model = self.note_repo.get_note_group(group_id, user_id)

        if not group_model:
            return None

        return self._group_model_to_dict(group_model)

    def list_note_groups(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """List all note groups for a user."""
        group_models = self.note_repo.get_user_note_groups(user_id, limit, offset)
        return [self._group_model_to_dict(g) for g in group_models]

    def update_note_group(
        self,
        group_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Optional[dict]:
        """Update a note group."""
        # Get existing group
        group_model = self.note_repo.get_note_group(group_id, user_id)
        if not group_model:
            return None

        # Build update dict
        updates = {}
        if name is not None:
            # Validate via domain entity
            temp_entity = NoteGroup.create(user_id, name)
            updates['name'] = temp_entity.name

        if color is not None:
            # Validate color
            if color not in NoteGroup.VALID_COLORS:
                raise ValueError(f"Invalid color: {color}")
            updates['color'] = color

        if icon is not None:
            updates['icon'] = icon

        if sort_order is not None:
            updates['sort_order'] = sort_order

        if updates:
            updated_model = self.note_repo.update_note_group(group_id, user_id, **updates)
            return self._group_model_to_dict(updated_model)

        return self._group_model_to_dict(group_model)

    def delete_note_group(self, group_id: UUID, user_id: UUID) -> bool:
        """Delete a note group."""
        return self.note_repo.delete_note_group(group_id, user_id)

    # ==================== Note Use Cases ====================

    def create_note(
        self,
        user_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        color: str = "yellow",
        is_pinned: bool = False,
        is_checklist: bool = False,
        group_id: Optional[UUID] = None,
        items: Optional[List[dict]] = None,
        categories: Optional[List[str]] = None,
    ) -> dict:
        """Create a new note."""
        # Convert item dicts to NoteItem entities if checklist
        item_entities = []
        if is_checklist and items:
            for item_data in items:
                item_entity = NoteItem.create(
                    content=item_data.get("content", ""),
                    is_checked=item_data.get("is_checked", False),
                    sort_order=item_data.get("sort_order", 0),
                )
                item_entities.append(item_entity)

        # Use domain entity for validation
        note_entity = Note.create(
            user_id=user_id,
            title=title,
            content=content,
            color=color,
            is_pinned=is_pinned,
            is_checklist=is_checklist,
            group_id=group_id,
            items=item_entities,
            categories=categories,
        )

        # Create in database
        note_model = self.note_repo.create_note(
            user_id=user_id,
            title=note_entity.title,
            content=note_entity.content,
            color=note_entity.color,
            is_pinned=note_entity.is_pinned,
            is_checklist=note_entity.is_checklist,
            group_id=note_entity.group_id,
            categories=note_entity.categories,
        )

        # Add items if checklist
        if is_checklist and item_entities:
            for item in item_entities:
                self.note_repo.create_note_item(
                    note_id=note_model.id,
                    content=item.content,
                    is_checked=item.is_checked,
                    sort_order=item.sort_order,
                )
            # Refresh to get items
            note_model = self.note_repo.get_note(note_model.id, user_id)

        return self._note_model_to_dict(note_model)

    def get_note(
        self,
        note_id: UUID,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> Optional[dict]:
        """Get a note by ID."""
        note_model = self.note_repo.get_note(note_id, user_id, include_deleted)

        if not note_model:
            return None

        return self._note_model_to_dict(note_model)

    def list_notes(
        self,
        user_id: UUID,
        group_id: Optional[UUID] = None,
        include_deleted: bool = False,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """List notes for a user with optional filters."""
        note_models = self.note_repo.get_user_notes(
            user_id,
            group_id=group_id,
            include_deleted=include_deleted,
            search=search,
            limit=limit,
            offset=offset,
        )
        return [self._note_model_to_dict(n) for n in note_models]

    def get_note_count(
        self,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> int:
        """Get the count of notes for a user."""
        return self.note_repo.get_note_count(user_id, include_deleted)

    def update_note(
        self,
        note_id: UUID,
        user_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        color: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        group_id: Optional[UUID] = None,
        categories: Optional[List[str]] = None,
    ) -> Optional[dict]:
        """Update a note."""
        # Get existing note
        note_model = self.note_repo.get_note(note_id, user_id)
        if not note_model:
            return None

        # Build update dict
        updates = {}

        if title is not None:
            if len(title) > 500:
                raise ValueError("Title cannot exceed 500 characters")
            updates['title'] = title.strip() if title else None

        if content is not None:
            updates['content'] = content.strip() if content else None

        if color is not None:
            if color not in Note.VALID_COLORS:
                raise ValueError(f"Invalid color: {color}")
            updates['color'] = color

        if is_pinned is not None:
            updates['is_pinned'] = is_pinned

        if group_id is not None:
            updates['group_id'] = group_id

        if categories is not None:
            updates['categories'] = categories

        if updates:
            updated_model = self.note_repo.update_note(note_id, user_id, **updates)
            return self._note_model_to_dict(updated_model)

        return self._note_model_to_dict(note_model)

    def delete_note(
        self,
        note_id: UUID,
        user_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """Delete a note (soft or hard)."""
        if soft_delete:
            return self.note_repo.soft_delete_note(note_id, user_id)
        else:
            return self.note_repo.hard_delete_note(note_id, user_id)

    def restore_note(self, note_id: UUID, user_id: UUID) -> Optional[dict]:
        """Restore a soft-deleted note."""
        note_model = self.note_repo.restore_note(note_id, user_id)

        if not note_model:
            return None

        return self._note_model_to_dict(note_model)

    # ==================== Note Item Use Cases ====================

    def create_note_item(
        self,
        note_id: UUID,
        user_id: UUID,
        content: str,
        is_checked: bool = False,
        sort_order: int = 0,
    ) -> Optional[dict]:
        """Create a note item (checklist item)."""
        # Verify note ownership
        note_model = self.note_repo.get_note(note_id, user_id)
        if not note_model:
            return None

        # Use domain entity for validation
        item_entity = NoteItem.create(content, is_checked, sort_order)

        # Create in database
        item_model = self.note_repo.create_note_item(
            note_id=note_id,
            content=item_entity.content,
            is_checked=item_entity.is_checked,
            sort_order=item_entity.sort_order,
        )

        if not item_model:
            return None

        return self._item_model_to_dict(item_model)

    def update_note_item(
        self,
        note_id: UUID,
        item_id: UUID,
        user_id: UUID,
        content: Optional[str] = None,
        is_checked: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> Optional[dict]:
        """Update a note item."""
        # Verify note ownership
        note_model = self.note_repo.get_note(note_id, user_id)
        if not note_model:
            return None

        # Build update dict
        updates = {}
        if content is not None:
            if not content or len(content.strip()) == 0:
                raise ValueError("Item content cannot be empty")
            updates['content'] = content.strip()

        if is_checked is not None:
            updates['is_checked'] = is_checked

        if sort_order is not None:
            updates['sort_order'] = sort_order

        if updates:
            updated_model = self.note_repo.update_note_item(item_id, note_id, **updates)
            if updated_model:
                return self._item_model_to_dict(updated_model)

        return None

    def delete_note_item(
        self,
        note_id: UUID,
        item_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a note item."""
        # Verify note ownership
        note_model = self.note_repo.get_note(note_id, user_id)
        if not note_model:
            return False

        return self.note_repo.delete_note_item(item_id, note_id)

    # ==================== Helper Methods ====================

    def _group_model_to_dict(self, model) -> dict:
        """Convert NoteGroupModel to dict."""
        return {
            "id": str(model.id),
            "user_id": str(model.user_id),
            "name": model.name,
            "color": model.color,
            "icon": model.icon,
            "sort_order": model.sort_order,
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
        }

    def _note_model_to_dict(self, model) -> dict:
        """Convert NoteModel to dict."""
        return {
            "id": str(model.id),
            "user_id": str(model.user_id),
            "group_id": str(model.group_id) if model.group_id else None,
            "title": model.title,
            "content": model.content,
            "color": model.color,
            "is_pinned": model.is_pinned,
            "is_checklist": model.is_checklist,
            "categories": model.categories or [],
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
            "deleted_at": model.deleted_at.isoformat() if model.deleted_at else None,
            "items": [self._item_model_to_dict(item) for item in model.items] if model.items else [],
        }

    def _item_model_to_dict(self, model) -> dict:
        """Convert NoteItemModel to dict."""
        return {
            "id": str(model.id),
            "note_id": str(model.note_id),
            "content": model.content,
            "is_checked": model.is_checked,
            "sort_order": model.sort_order,
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
        }
