"""
Inbox router - CRUD endpoints for inbox item management with AI processing.
Part of Presentation layer.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.dependencies import get_db, get_current_user
from app.application.use_cases.inbox_use_cases import InboxUseCases


router = APIRouter(prefix="/inbox", tags=["inbox"])


# ==================== Request/Response Models ====================


class InboxItemCreateRequest(BaseModel):
    """Request to create an inbox item."""
    type: str = Field(..., pattern="^(email|calendar_event|message|notification|web_clip|file|manual)$")
    source: str = Field(..., min_length=1, max_length=100)
    subject: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    priority: str = Field("medium", pattern="^(low|medium|high|urgent)$")


class InboxItemModifyRequest(BaseModel):
    """Request to modify and accept an inbox item."""
    action: str = Field(..., pattern="^(create_task|create_note|archive|delegate)$")
    data: Dict[str, Any] = Field(default_factory=dict)


class InboxItemRejectRequest(BaseModel):
    """Request to reject an inbox item."""
    reason: Optional[str] = None


class InboxItemResponse(BaseModel):
    """Inbox item response model."""
    id: str
    user_id: str
    type: str
    source: str
    status: str
    priority: str
    subject: Optional[str]
    content: Optional[str]
    raw_data: Dict[str, Any]
    ai_suggestion: Optional[Dict[str, Any]]
    user_decision: Optional[Dict[str, Any]]
    linked_items: List[Dict[str, Any]]
    processed_at: Optional[str]
    created_at: str
    updated_at: str


class InboxListResponse(BaseModel):
    """Inbox list response model."""
    items: List[InboxItemResponse]
    total: int
    skip: int
    limit: int


class InboxProcessResultResponse(BaseModel):
    """Response for processing an inbox item."""
    inbox_item: InboxItemResponse
    created_item: Optional[Dict[str, Any]]


class InboxCountResponse(BaseModel):
    """Count of unprocessed inbox items."""
    count: int


# ==================== Endpoints ====================


@router.post("", response_model=InboxItemResponse, status_code=status.HTTP_201_CREATED)
def create_inbox_item(
    request: InboxItemCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new inbox item.
    """
    try:
        from app.domain.entities.inbox_item import InboxItemType, Priority

        use_cases = InboxUseCases(db)
        item = use_cases.create_inbox_item(
            user_id=UUID(current_user["id"]),
            type=InboxItemType(request.type),
            source=request.source,
            subject=request.subject,
            content=request.content,
            raw_data=request.raw_data,
            priority=Priority(request.priority),
        )
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create inbox item: {str(e)}",
        )


@router.get("", response_model=InboxListResponse)
def list_inbox_items(
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    priority: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List inbox items for the current user with optional filters.

    Filters:
    - status: comma-separated list (unprocessed, pending_review, accepted, modified, rejected, archived)
    - type: comma-separated list (email, calendar_event, message, etc.)
    - priority: comma-separated list (low, medium, high, urgent)
    """
    try:
        use_cases = InboxUseCases(db)
        result = use_cases.get_inbox_items(
            user_id=UUID(current_user["id"]),
            status=status_filter,
            type=type_filter,
            priority=priority,
            skip=skip,
            limit=limit,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list inbox items: {str(e)}",
        )


@router.get("/count", response_model=InboxCountResponse)
def get_unprocessed_count(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get count of unprocessed inbox items.
    """
    try:
        use_cases = InboxUseCases(db)
        count = use_cases.get_unprocessed_count(user_id=UUID(current_user["id"]))
        return {"count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get count: {str(e)}",
        )


@router.get("/{item_id}", response_model=InboxItemResponse)
def get_inbox_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a single inbox item by ID.
    """
    try:
        use_cases = InboxUseCases(db)
        item = use_cases.get_inbox_item(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get inbox item: {str(e)}",
        )


@router.post("/{item_id}/suggest", response_model=InboxItemResponse)
async def request_ai_suggestion(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Request AI suggestion for processing an inbox item.
    """
    try:
        use_cases = InboxUseCases(db)
        item = await use_cases.request_ai_suggestion(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get AI suggestion: {str(e)}",
        )


@router.post("/{item_id}/accept", response_model=InboxProcessResultResponse)
async def accept_suggestion(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Accept the AI suggestion and execute the action.
    Creates the suggested task/note/event and marks the inbox item as processed.
    """
    try:
        use_cases = InboxUseCases(db)
        result = await use_cases.accept_suggestion(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found or has no suggestion",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to accept suggestion: {str(e)}",
        )


@router.post("/{item_id}/modify", response_model=InboxProcessResultResponse)
def modify_and_accept(
    item_id: UUID,
    request: InboxItemModifyRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Accept with modifications and execute the action.
    Creates the item with user modifications instead of AI suggestion.
    """
    try:
        use_cases = InboxUseCases(db)
        result = use_cases.modify_and_accept(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
            modifications={
                "action": request.action,
                "data": request.data,
            },
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to modify and accept: {str(e)}",
        )


@router.post("/{item_id}/reject", response_model=InboxItemResponse)
def reject_item(
    item_id: UUID,
    request: InboxItemRejectRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Reject the inbox item.
    Marks the item as rejected without creating any task/note/event.
    """
    try:
        use_cases = InboxUseCases(db)
        item = use_cases.reject_item(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
            reason=request.reason,
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject item: {str(e)}",
        )


@router.post("/{item_id}/archive", response_model=InboxItemResponse)
def archive_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Archive the inbox item without processing.
    """
    try:
        use_cases = InboxUseCases(db)
        item = use_cases.archive_item(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive item: {str(e)}",
        )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete an inbox item.
    """
    try:
        use_cases = InboxUseCases(db)
        success = use_cases.delete_item(
            item_id=item_id,
            user_id=UUID(current_user["id"]),
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found",
            )

        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete item: {str(e)}",
        )
