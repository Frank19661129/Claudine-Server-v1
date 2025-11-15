"""
Note domain entity.
Part of Domain layer - contains business logic and rules.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class NoteItem:
    """
    NoteItem represents a single item in a checklist note.
    """

    id: Optional[UUID]
    note_id: Optional[UUID]
    content: str
    is_checked: bool
    sort_order: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        content: str,
        is_checked: bool = False,
        sort_order: int = 0,
    ) -> "NoteItem":
        """Create a new note item."""
        if not content or len(content.strip()) == 0:
            raise ValueError("Note item content cannot be empty")

        return cls(
            id=None,
            note_id=None,
            content=content.strip(),
            is_checked=is_checked,
            sort_order=sort_order,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def toggle_checked(self) -> None:
        """Toggle the checked status."""
        self.is_checked = not self.is_checked
        self.updated_at = datetime.utcnow()

    def update_content(self, new_content: str) -> None:
        """Update the item content."""
        if not new_content or len(new_content.strip()) == 0:
            raise ValueError("Note item content cannot be empty")

        self.content = new_content.strip()
        self.updated_at = datetime.utcnow()


@dataclass
class Note:
    """
    Note domain entity.
    Represents a note that can be text-based or a checklist.
    """

    id: Optional[UUID]
    user_id: UUID
    group_id: Optional[UUID]
    title: Optional[str]
    content: Optional[str]
    color: str
    is_pinned: bool
    is_checklist: bool
    items: List[NoteItem] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    # Valid color values
    VALID_COLORS = ["yellow", "blue", "red", "green", "purple", "orange", "pink", "gray", "white"]

    @classmethod
    def create(
        cls,
        user_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        color: str = "yellow",
        is_pinned: bool = False,
        is_checklist: bool = False,
        group_id: Optional[UUID] = None,
        items: Optional[List[NoteItem]] = None,
        categories: Optional[List[str]] = None,
    ) -> "Note":
        """
        Factory method to create a new note.
        Enforces business rules at creation time.
        """
        # Validate title length if provided
        if title and len(title) > 500:
            raise ValueError("Note title cannot exceed 500 characters")

        # Validate color
        if color not in cls.VALID_COLORS:
            raise ValueError(
                f"Invalid color: {color}. Must be one of: {', '.join(cls.VALID_COLORS)}"
            )

        # If checklist mode, ensure we have items
        if is_checklist and not items:
            items = []

        # If not checklist mode, items should be empty
        if not is_checklist and items:
            raise ValueError("Items can only be added to checklist notes")

        return cls(
            id=None,  # Will be set by repository
            user_id=user_id,
            group_id=group_id,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            color=color,
            is_pinned=is_pinned,
            is_checklist=is_checklist,
            items=items or [],
            categories=categories or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            deleted_at=None,
        )

    def update_title(self, new_title: Optional[str]) -> None:
        """Update the note title."""
        if new_title and len(new_title) > 500:
            raise ValueError("Note title cannot exceed 500 characters")

        self.title = new_title.strip() if new_title else None
        self.updated_at = datetime.utcnow()

    def update_content(self, new_content: Optional[str]) -> None:
        """Update the note content."""
        self.content = new_content.strip() if new_content else None
        self.updated_at = datetime.utcnow()

    def update_color(self, new_color: str) -> None:
        """Update the note color."""
        if new_color not in self.VALID_COLORS:
            raise ValueError(
                f"Invalid color: {new_color}. Must be one of: {', '.join(self.VALID_COLORS)}"
            )

        self.color = new_color
        self.updated_at = datetime.utcnow()

    def toggle_pinned(self) -> None:
        """Toggle the pinned status."""
        self.is_pinned = not self.is_pinned
        self.updated_at = datetime.utcnow()

    def move_to_group(self, group_id: Optional[UUID]) -> None:
        """Move the note to a different group."""
        self.group_id = group_id
        self.updated_at = datetime.utcnow()

    def add_item(self, item: NoteItem) -> None:
        """Add an item to a checklist note."""
        if not self.is_checklist:
            raise ValueError("Can only add items to checklist notes")

        self.items.append(item)
        self.updated_at = datetime.utcnow()

    def remove_item(self, item_id: UUID) -> None:
        """Remove an item from a checklist note."""
        if not self.is_checklist:
            raise ValueError("Can only remove items from checklist notes")

        self.items = [item for item in self.items if item.id != item_id]
        self.updated_at = datetime.utcnow()

    def soft_delete(self) -> None:
        """Soft delete the note."""
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore a soft-deleted note."""
        if not self.deleted_at:
            raise ValueError("Note is not deleted")

        self.deleted_at = None
        self.updated_at = datetime.utcnow()

    def is_deleted(self) -> bool:
        """Check if the note is deleted."""
        return self.deleted_at is not None
