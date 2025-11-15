"""
Notes router - CRUD endpoints for note management.
Part of Presentation layer.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.dependencies import get_db, get_current_user
from app.application.use_cases.note_use_cases import NoteUseCases


router = APIRouter(prefix="/notes", tags=["notes"])


# ==================== Request/Response Models ====================

# Note Group Models
class NoteGroupCreateRequest(BaseModel):
    """Request to create a note group."""
    name: str = Field(..., min_length=1, max_length=255)
    color: str = Field("blue", pattern="^(blue|red|green|yellow|purple|orange|pink|gray)$")
    icon: Optional[str] = Field(None, max_length=50)
    sort_order: int = Field(0, ge=0)


class NoteGroupUpdateRequest(BaseModel):
    """Request to update a note group."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    color: Optional[str] = Field(None, pattern="^(blue|red|green|yellow|purple|orange|pink|gray)$")
    icon: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = Field(None, ge=0)


class NoteGroupResponse(BaseModel):
    """Note group response model."""
    id: str
    user_id: str
    name: str
    color: str
    icon: Optional[str]
    sort_order: int
    created_at: str
    updated_at: str


class NoteGroupListResponse(BaseModel):
    """List of note groups."""
    groups: List[NoteGroupResponse]
    total: int


# Note Item Models
class NoteItemData(BaseModel):
    """Note item data for creating/updating."""
    content: str = Field(..., min_length=1)
    is_checked: bool = False
    sort_order: int = 0


class NoteItemCreateRequest(BaseModel):
    """Request to create a note item."""
    content: str = Field(..., min_length=1)
    is_checked: bool = False
    sort_order: int = 0


class NoteItemUpdateRequest(BaseModel):
    """Request to update a note item."""
    content: Optional[str] = Field(None, min_length=1)
    is_checked: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


class NoteItemResponse(BaseModel):
    """Note item response model."""
    id: str
    note_id: str
    content: str
    is_checked: bool
    sort_order: int
    created_at: str
    updated_at: str


# Note Models
class NoteCreateRequest(BaseModel):
    """Request to create a note."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    color: str = Field("yellow", pattern="^(yellow|blue|red|green|purple|orange|pink|gray|white)$")
    is_pinned: bool = False
    is_checklist: bool = False
    group_id: Optional[str] = None
    items: Optional[List[NoteItemData]] = []
    categories: Optional[List[str]] = []


class NoteUpdateRequest(BaseModel):
    """Request to update a note."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^(yellow|blue|red|green|purple|orange|pink|gray|white)$")
    is_pinned: Optional[bool] = None
    group_id: Optional[str] = None
    categories: Optional[List[str]] = None


class NoteResponse(BaseModel):
    """Note response model."""
    id: str
    user_id: str
    group_id: Optional[str]
    title: Optional[str]
    content: Optional[str]
    color: str
    is_pinned: bool
    is_checklist: bool
    created_at: str
    updated_at: str
    deleted_at: Optional[str]
    items: List[NoteItemResponse]
    categories: List[str] = []


class NoteListResponse(BaseModel):
    """List of notes."""
    notes: List[NoteResponse]
    total: int


# ==================== Note Group Endpoints ====================


@router.post("/groups", response_model=NoteGroupResponse, status_code=status.HTTP_201_CREATED)
def create_note_group(
    request: NoteGroupCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new note group."""
    try:
        use_cases = NoteUseCases(db)
        group = use_cases.create_note_group(
            user_id=UUID(current_user["id"]),
            name=request.name,
            color=request.color,
            icon=request.icon,
            sort_order=request.sort_order,
        )
        return group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note group: {str(e)}"
        )


@router.get("/groups", response_model=NoteGroupListResponse)
def list_note_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all note groups for the current user."""
    try:
        use_cases = NoteUseCases(db)
        groups = use_cases.list_note_groups(
            user_id=UUID(current_user["id"]),
            limit=limit,
            offset=skip,
        )
        return {"groups": groups, "total": len(groups)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list note groups: {str(e)}"
        )


@router.get("/groups/{group_id}", response_model=NoteGroupResponse)
def get_note_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific note group."""
    try:
        use_cases = NoteUseCases(db)
        group = use_cases.get_note_group(
            group_id=UUID(group_id),
            user_id=UUID(current_user["id"]),
        )
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note group not found")
        return group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get note group: {str(e)}"
        )


@router.put("/groups/{group_id}", response_model=NoteGroupResponse)
def update_note_group(
    group_id: str,
    request: NoteGroupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a note group."""
    try:
        use_cases = NoteUseCases(db)
        group = use_cases.update_note_group(
            group_id=UUID(group_id),
            user_id=UUID(current_user["id"]),
            name=request.name,
            color=request.color,
            icon=request.icon,
            sort_order=request.sort_order,
        )
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note group not found")
        return group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update note group: {str(e)}"
        )


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a note group."""
    try:
        use_cases = NoteUseCases(db)
        success = use_cases.delete_note_group(
            group_id=UUID(group_id),
            user_id=UUID(current_user["id"]),
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note group not found")
        return
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete note group: {str(e)}"
        )


# ==================== Note Endpoints ====================


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    request: NoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new note."""
    try:
        use_cases = NoteUseCases(db)

        # Convert items to dicts if present
        items_data = None
        if request.items:
            items_data = [item.dict() for item in request.items]

        note = use_cases.create_note(
            user_id=UUID(current_user["id"]),
            title=request.title,
            content=request.content,
            color=request.color,
            is_pinned=request.is_pinned,
            is_checklist=request.is_checklist,
            group_id=UUID(request.group_id) if request.group_id else None,
            items=items_data,
            categories=request.categories,
        )
        return note
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note: {str(e)}"
        )


@router.get("", response_model=NoteListResponse)
def list_notes(
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    include_deleted: bool = Query(False, description="Include soft-deleted notes"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List notes for the current user."""
    try:
        use_cases = NoteUseCases(db)
        notes = use_cases.list_notes(
            user_id=UUID(current_user["id"]),
            group_id=UUID(group_id) if group_id else None,
            include_deleted=include_deleted,
            search=search,
            limit=limit,
            offset=skip,
        )
        total = use_cases.get_note_count(
            user_id=UUID(current_user["id"]),
            include_deleted=include_deleted,
        )
        return {"notes": notes, "total": total}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list notes: {str(e)}"
        )


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific note."""
    try:
        use_cases = NoteUseCases(db)
        note = use_cases.get_note(
            note_id=UUID(note_id),
            user_id=UUID(current_user["id"]),
        )
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return note
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get note: {str(e)}"
        )


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: str,
    request: NoteUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a note."""
    try:
        use_cases = NoteUseCases(db)
        note = use_cases.update_note(
            note_id=UUID(note_id),
            user_id=UUID(current_user["id"]),
            title=request.title,
            content=request.content,
            color=request.color,
            is_pinned=request.is_pinned,
            group_id=UUID(request.group_id) if request.group_id else None,
            categories=request.categories,
        )
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return note
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update note: {str(e)}"
        )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (true) or soft delete (false)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a note."""
    try:
        use_cases = NoteUseCases(db)
        success = use_cases.delete_note(
            note_id=UUID(note_id),
            user_id=UUID(current_user["id"]),
            soft_delete=not hard_delete,
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete note: {str(e)}"
        )


@router.post("/{note_id}/restore", response_model=NoteResponse)
def restore_note(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Restore a soft-deleted note."""
    try:
        use_cases = NoteUseCases(db)
        note = use_cases.restore_note(
            note_id=UUID(note_id),
            user_id=UUID(current_user["id"]),
        )
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or not deleted")
        return note
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore note: {str(e)}"
        )


# ==================== Note Item Endpoints ====================


@router.post("/{note_id}/items", response_model=NoteItemResponse, status_code=status.HTTP_201_CREATED)
def create_note_item(
    note_id: str,
    request: NoteItemCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add an item to a checklist note."""
    try:
        use_cases = NoteUseCases(db)
        item = use_cases.create_note_item(
            note_id=UUID(note_id),
            user_id=UUID(current_user["id"]),
            content=request.content,
            is_checked=request.is_checked,
            sort_order=request.sort_order,
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or not a checklist")
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note item: {str(e)}"
        )


@router.put("/{note_id}/items/{item_id}", response_model=NoteItemResponse)
def update_note_item(
    note_id: str,
    item_id: str,
    request: NoteItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a checklist item."""
    try:
        use_cases = NoteUseCases(db)
        item = use_cases.update_note_item(
            note_id=UUID(note_id),
            item_id=UUID(item_id),
            user_id=UUID(current_user["id"]),
            content=request.content,
            is_checked=request.is_checked,
            sort_order=request.sort_order,
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note item not found")
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update note item: {str(e)}"
        )


@router.delete("/{note_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note_item(
    note_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a checklist item."""
    try:
        use_cases = NoteUseCases(db)
        success = use_cases.delete_note_item(
            note_id=UUID(note_id),
            item_id=UUID(item_id),
            user_id=UUID(current_user["id"]),
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note item not found")
        return
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete note item: {str(e)}"
        )
