"""
Note repository - data access layer.
Part of Infrastructure layer.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import desc, or_, and_

from app.infrastructure.database.models import NoteModel, NoteGroupModel, NoteItemModel
from app.domain.entities.note import Note, NoteItem
from app.domain.entities.note_group import NoteGroup


class NoteRepository:
    """Repository for note and note_group persistence operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Note Group Methods ====================

    def create_note_group(
        self,
        user_id: UUID,
        name: str,
        color: str = "blue",
        icon: Optional[str] = None,
        sort_order: int = 0,
    ) -> NoteGroupModel:
        """Create a new note group."""
        group = NoteGroupModel(
            user_id=user_id,
            name=name,
            color=color,
            icon=icon,
            sort_order=sort_order,
        )

        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)

        return group

    def get_note_group(
        self,
        group_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[NoteGroupModel]:
        """Get a note group by ID."""
        query = self.db.query(NoteGroupModel).filter(NoteGroupModel.id == group_id)

        if user_id:
            query = query.filter(NoteGroupModel.user_id == user_id)

        return query.first()

    def get_user_note_groups(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NoteGroupModel]:
        """Get all note groups for a user."""
        return (
            self.db.query(NoteGroupModel)
            .filter(NoteGroupModel.user_id == user_id)
            .order_by(NoteGroupModel.sort_order, NoteGroupModel.name)
            .limit(limit)
            .offset(offset)
            .all()
        )

    def update_note_group(
        self,
        group_id: UUID,
        user_id: UUID,
        **updates
    ) -> Optional[NoteGroupModel]:
        """Update a note group."""
        group = self.get_note_group(group_id, user_id)
        if not group:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(group, key):
                setattr(group, key, value)

        self.db.commit()
        self.db.refresh(group)

        return group

    def delete_note_group(
        self,
        group_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a note group."""
        group = self.get_note_group(group_id, user_id)
        if not group:
            return False

        self.db.delete(group)
        self.db.commit()

        return True

    # ==================== Note Methods ====================

    def create_note(
        self,
        user_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        color: str = "yellow",
        is_pinned: bool = False,
        is_checklist: bool = False,
        group_id: Optional[UUID] = None,
        categories: Optional[List[str]] = None,
    ) -> NoteModel:
        """Create a new note."""
        note = NoteModel(
            user_id=user_id,
            group_id=group_id,
            title=title,
            content=content,
            color=color,
            is_pinned=is_pinned,
            is_checklist=is_checklist,
            categories=categories or [],
        )

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def get_note(
        self,
        note_id: UUID,
        user_id: Optional[UUID] = None,
        include_deleted: bool = False,
    ) -> Optional[NoteModel]:
        """Get a note by ID."""
        query = self.db.query(NoteModel).options(
            joinedload(NoteModel.group),
            joinedload(NoteModel.items)
        ).filter(NoteModel.id == note_id)

        if user_id:
            query = query.filter(NoteModel.user_id == user_id)

        if not include_deleted:
            query = query.filter(NoteModel.deleted_at.is_(None))

        return query.first()

    def get_user_notes(
        self,
        user_id: UUID,
        group_id: Optional[UUID] = None,
        include_deleted: bool = False,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NoteModel]:
        """Get notes for a user with optional filters."""
        query = self.db.query(NoteModel).options(
            joinedload(NoteModel.group),
            joinedload(NoteModel.items)
        ).filter(NoteModel.user_id == user_id)

        if not include_deleted:
            query = query.filter(NoteModel.deleted_at.is_(None))

        if group_id:
            query = query.filter(NoteModel.group_id == group_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    NoteModel.title.ilike(search_pattern),
                    NoteModel.content.ilike(search_pattern)
                )
            )

        # Order: pinned first, then by updated_at desc
        query = query.order_by(
            desc(NoteModel.is_pinned),
            desc(NoteModel.updated_at)
        )

        return query.limit(limit).offset(offset).all()

    def get_note_count(
        self,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> int:
        """Get the count of notes for a user."""
        query = self.db.query(NoteModel).filter(NoteModel.user_id == user_id)

        if not include_deleted:
            query = query.filter(NoteModel.deleted_at.is_(None))

        return query.count()

    def update_note(
        self,
        note_id: UUID,
        user_id: UUID,
        **updates
    ) -> Optional[NoteModel]:
        """Update a note."""
        note = self.get_note(note_id, user_id)
        if not note:
            return None

        for key, value in updates.items():
            if hasattr(note, key):
                setattr(note, key, value)

        self.db.commit()
        self.db.refresh(note)

        return note

    def soft_delete_note(
        self,
        note_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete a note."""
        from datetime import datetime

        note = self.get_note(note_id, user_id)
        if not note:
            return False

        note.deleted_at = datetime.utcnow()
        self.db.commit()

        return True

    def hard_delete_note(
        self,
        note_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Permanently delete a note."""
        note = self.get_note(note_id, user_id, include_deleted=True)
        if not note:
            return False

        self.db.delete(note)
        self.db.commit()

        return True

    def restore_note(
        self,
        note_id: UUID,
        user_id: UUID,
    ) -> Optional[NoteModel]:
        """Restore a soft-deleted note."""
        note = self.get_note(note_id, user_id, include_deleted=True)
        if not note or not note.deleted_at:
            return None

        note.deleted_at = None
        self.db.commit()
        self.db.refresh(note)

        return note

    # ==================== Note Item Methods ====================

    def create_note_item(
        self,
        note_id: UUID,
        content: str,
        is_checked: bool = False,
        sort_order: int = 0,
    ) -> Optional[NoteItemModel]:
        """Create a note item (checklist item)."""
        # Verify note exists and is a checklist
        note = self.db.query(NoteModel).filter(NoteModel.id == note_id).first()
        if not note or not note.is_checklist:
            return None

        item = NoteItemModel(
            note_id=note_id,
            content=content,
            is_checked=is_checked,
            sort_order=sort_order,
        )

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def get_note_item(
        self,
        item_id: UUID,
        note_id: UUID,
    ) -> Optional[NoteItemModel]:
        """Get a note item by ID."""
        return (
            self.db.query(NoteItemModel)
            .filter(
                and_(
                    NoteItemModel.id == item_id,
                    NoteItemModel.note_id == note_id
                )
            )
            .first()
        )

    def update_note_item(
        self,
        item_id: UUID,
        note_id: UUID,
        **updates
    ) -> Optional[NoteItemModel]:
        """Update a note item."""
        item = self.get_note_item(item_id, note_id)
        if not item:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)

        return item

    def delete_note_item(
        self,
        item_id: UUID,
        note_id: UUID,
    ) -> bool:
        """Delete a note item."""
        item = self.get_note_item(item_id, note_id)
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()

        return True
