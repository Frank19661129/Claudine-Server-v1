"""
Conversation router - Chat and AI conversation endpoints.
Part of Presentation layer.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.dependencies import get_db, get_current_user
from app.application.use_cases.conversation_use_cases import ConversationUseCases


router = APIRouter(prefix="/conversations", tags=["conversations"])


# ==================== Request/Response Models ====================


class ConversationCreateRequest(BaseModel):
    """Request to create a conversation."""
    mode: str = Field(default="chat", pattern="^(chat|voice|note|scan)$")
    title: Optional[str] = Field(None, max_length=500)


class MessageSendRequest(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=10000)
    stream: bool = Field(default=False, description="Stream response via SSE")
    test_mode: int = Field(default=0, ge=0, le=2, description="Test mode: 0=normal, 1=log only, 2=log+confirm")


class MessageResponse(BaseModel):
    """Message response."""
    id: str
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response."""
    id: UUID
    user_id: UUID
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    latest_message: Optional[MessageResponse] = None

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with messages."""
    id: UUID
    user_id: UUID
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


# ==================== Endpoints ====================


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new conversation.

    Modes:
    - chat: Text chat (default)
    - voice: Voice conversation
    - note: Quick note taking
    - scan: Document scanning
    """
    try:
        use_cases = ConversationUseCases(db)
        conversation = use_cases.create_conversation(
            user_id=current_user["id"],
            mode=request.mode,
            title=request.title,
        )

        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            mode=conversation.mode,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=0,
            latest_message=None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}",
        )


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    mode: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List user's conversations.

    Query params:
    - mode: Filter by mode (chat, voice, note, scan)
    - limit: Max results (default 50)
    - offset: Pagination offset
    """
    try:
        use_cases = ConversationUseCases(db)
        conversations = use_cases.get_user_conversations(
            user_id=current_user["id"],
            mode=mode,
            limit=limit,
            offset=offset,
        )

        return [
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                mode=conv.mode,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=conv.message_count(),
                latest_message=MessageResponse(
                    id=conv.messages[-1].id,
                    conversation_id=conv.messages[-1].conversation_id,
                    role=conv.messages[-1].role,
                    content=conv.messages[-1].content[:100] + ("..." if len(conv.messages[-1].content) > 100 else ""),
                    created_at=conv.messages[-1].created_at,
                    metadata=conv.messages[-1].metadata,
                ) if conv.messages else None,
            )
            for conv in conversations
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list conversations: {str(e)}",
        )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a conversation with all messages."""
    try:
        use_cases = ConversationUseCases(db)
        conversation = use_cases.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user["id"],
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return ConversationDetailResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            mode=conversation.mode,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[
                MessageResponse(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at,
                    metadata=msg.metadata,
                )
                for msg in conversation.messages
            ],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}",
        )


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: UUID,
    request: MessageSendRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message in a conversation.

    Supports:
    - Regular chat messages
    - Command keywords (#calendar, #note, #scan, #help)
    - Streaming via Server-Sent Events (set stream=true)

    For streaming, use GET /{conversation_id}/messages/stream endpoint instead.
    """
    # If streaming requested, return error - use streaming endpoint
    if request.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="For streaming, use GET /{conversation_id}/messages/stream endpoint",
        )

    try:
        use_cases = ConversationUseCases(db)
        response_message = await use_cases.send_message(
            conversation_id=conversation_id,
            user_id=current_user["id"],
            content=request.content,
        )

        return MessageResponse(
            id=response_message.id,
            conversation_id=response_message.conversation_id,
            role=response_message.role,
            content=response_message.content,
            created_at=response_message.created_at,
            metadata=response_message.metadata,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        )


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: UUID,
    request: MessageSendRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message and stream the response via Server-Sent Events.

    Returns:
        StreamingResponse with text/event-stream content-type
    """
    try:
        use_cases = ConversationUseCases(db)

        async def event_generator():
            """Generate SSE events."""
            import json
            import re
            try:
                async for chunk in use_cases.send_message_stream(
                    conversation_id=conversation_id,
                    user_id=current_user["id"],
                    content=request.content,
                    test_mode=request.test_mode,
                ):
                    # Check if this is a confirmation-required response (test_mode=2)
                    if "TEST MODE: Bevestiging vereist" in chunk and "Wacht op bevestiging" in chunk:
                        # Parse the tool details from the chunk
                        tool_match = re.search(r'Tool: (\w+)', chunk)
                        params_match = re.search(r'```json\n(.*?)\n```', chunk, re.DOTALL)
                        route_match = re.search(r'Route: (.+?) →', chunk)
                        provider_match = re.search(r'→ (\w+)\n', chunk)

                        tool_name = tool_match.group(1) if tool_match else "unknown"
                        tool_params = {}
                        if params_match:
                            try:
                                tool_params = json.loads(params_match.group(1))
                            except:
                                pass
                        provider = provider_match.group(1) if provider_match else None

                        # Send as confirm_required event
                        yield f"data: {json.dumps({'type': 'confirm_required', 'content': chunk, 'tool_name': tool_name, 'tool_params': tool_params, 'provider': provider})}\n\n"
                    else:
                        # Regular content
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                # Send completion event
                yield "data: [DONE]\n\n"

            except Exception as e:
                # Send error event
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream message: {str(e)}",
        )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    try:
        use_cases = ConversationUseCases(db)
        success = use_cases.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user["id"],
        )

        return {"success": success, "message": "Conversation deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}",
        )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get messages from a conversation with pagination."""
    try:
        use_cases = ConversationUseCases(db)
        messages = use_cases.get_messages(
            conversation_id=conversation_id,
            user_id=current_user["id"],
            limit=limit,
            offset=offset,
        )

        return [
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.metadata,
            )
            for msg in messages
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}",
        )


@router.post("/{conversation_id}/generate-title")
async def generate_conversation_title(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate an AI-powered title for a conversation.

    Uses Claude to analyze the conversation and create a short,
    descriptive title (2-5 words) similar to Claude Desktop's auto-titling.
    """
    try:
        use_cases = ConversationUseCases(db)
        title = await use_cases.generate_title(
            conversation_id=conversation_id,
            user_id=current_user["id"],
        )

        return {"title": title, "success": True}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate title: {str(e)}",
        )
