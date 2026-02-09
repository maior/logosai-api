"""User memory management endpoints.

Provides REST API for:
- Listing user memories
- Creating/updating/deleting memories
- Manual memory extraction from conversations
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DBSession
from app.core.security import verify_token
from app.models.logosus.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryExtractRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional HTTP Bearer for JWT auth
security = HTTPBearer(auto_error=False)


async def _get_user(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
    x_user_email: Optional[str] = None,
) -> User:
    """Resolve user from JWT or X-User-Email header."""
    user_service = UserService(db)

    # Try JWT first
    if credentials:
        try:
            payload = verify_token(credentials.credentials)
            if payload and payload.get("type") == "access":
                user_email = payload.get("email") or payload.get("sub")
                user = await user_service.get_by_email(user_email)
                if user:
                    return user
        except Exception:
            pass

    # Try X-User-Email header
    if x_user_email:
        user = await user_service.get_by_email(x_user_email)
        if user:
            return user

        # Auto-create for OAuth users
        from app.schemas.user import UserCreate
        user_data = UserCreate(
            email=x_user_email,
            name=x_user_email.split("@")[0],
        )
        user = await user_service.create(user_data)
        await db.commit()
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide JWT token or X-User-Email header.",
    )


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
    memory_type: Optional[str] = Query(None, description="Filter by type: fact, preference, context, instruction"),
    limit: int = Query(50, ge=1, le=200),
):
    """List user memories."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    memories = await service.get_memories_for_user(
        user_id=user.id,
        memory_type=memory_type,
        limit=limit,
    )

    return {
        "memories": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "memory_type": m.memory_type,
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
                "source_conversation_id": m.source_conversation_id,
                "is_active": m.is_active,
                "access_count": m.access_count,
                "last_accessed_at": m.last_accessed_at,
                "metadata": m.metadata_json,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in memories
        ],
        "total": len(memories),
    }


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MemoryResponse)
async def create_memory(
    data: MemoryCreate,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
):
    """Create a new user memory manually."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    memory = await service.create_memory(
        user_id=user.id,
        data=data.model_dump(),
    )
    await db.commit()
    await db.refresh(memory)

    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "category": memory.category,
        "importance": memory.importance,
        "source_conversation_id": memory.source_conversation_id,
        "is_active": memory.is_active,
        "access_count": memory.access_count,
        "last_accessed_at": memory.last_accessed_at,
        "metadata": memory.metadata_json,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
):
    """Get a single memory by ID."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    memory = await service.get_memory_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "category": memory.category,
        "importance": memory.importance,
        "source_conversation_id": memory.source_conversation_id,
        "is_active": memory.is_active,
        "access_count": memory.access_count,
        "last_accessed_at": memory.last_accessed_at,
        "metadata": memory.metadata_json,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
):
    """Update a user memory."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    memory = await service.get_memory_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    updated = await service.update_memory(
        memory,
        data.model_dump(exclude_unset=True),
    )
    await db.commit()
    await db.refresh(updated)

    return {
        "id": updated.id,
        "user_id": updated.user_id,
        "memory_type": updated.memory_type,
        "content": updated.content,
        "category": updated.category,
        "importance": updated.importance,
        "source_conversation_id": updated.source_conversation_id,
        "is_active": updated.is_active,
        "access_count": updated.access_count,
        "last_accessed_at": updated.last_accessed_at,
        "metadata": updated.metadata_json,
        "created_at": updated.created_at,
        "updated_at": updated.updated_at,
    }


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
):
    """Delete (soft-deactivate) a user memory."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    memory = await service.get_memory_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    await service.delete_memory(memory)
    await db.commit()


@router.post("/extract")
async def extract_memories(
    data: MemoryExtractRequest,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None),
):
    """Manually trigger memory extraction from a conversation."""
    user = await _get_user(credentials, db, x_user_email)
    service = MemoryService(db)

    # Load messages from conversation
    from app.services.conversation_service import ConversationService
    conv_service = ConversationService(db)
    messages = await conv_service.get_messages(data.conversation_id, user.id)

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or no messages",
        )

    # Format messages for extraction
    message_dicts = [
        {"role": m.role, "content": m.content}
        for m in messages
    ]

    # Extract
    new_memories = await service.extract_memories_from_conversation(
        user_id=user.id,
        conversation_id=data.conversation_id,
        messages=message_dicts,
    )

    return {
        "extracted": len(new_memories),
        "memories": [
            {
                "id": m.id,
                "memory_type": m.memory_type,
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
            }
            for m in new_memories
        ],
    }
