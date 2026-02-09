"""Session (Conversation) management endpoints.

Uses logosus schema where Conversation is for chat sessions.
Note: 'Session' naming is kept for API backward compatibility.
Supports both JWT and email-based authentication for OAuth users.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DBSession
from app.core.security import verify_token
from app.models.logosus.user import User
from app.schemas.session import (
    MessageListResponse,
    MessageResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional HTTP Bearer for JWT auth
security = HTTPBearer(auto_error=False)


async def get_user_from_request(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
    email: Optional[str] = None,
    x_user_email: Optional[str] = None,
) -> User:
    """
    Get user from JWT token or email parameter/header.

    Uses logosus schema where users have UUID as primary key.

    Priority:
    1. JWT Bearer token (if provided)
    2. X-User-Email header (for OAuth users)
    3. email query parameter (for OAuth users)
    """
    user_service = UserService(db)

    # Try JWT auth first
    if credentials:
        try:
            payload = verify_token(credentials.credentials)
            if payload and payload.get("type") == "access":
                user_email = payload.get("email") or payload.get("sub")
                user = await user_service.get_by_email(user_email)
                if user:
                    return user
        except Exception as e:
            logger.debug(f"JWT auth failed: {e}")

    # Try X-User-Email header
    actual_email = x_user_email or email
    if actual_email:
        user = await user_service.get_by_email(actual_email)
        if user:
            return user

        # Auto-create user if not exists (for OAuth)
        from app.schemas.user import UserCreate
        user_data = UserCreate(
            email=actual_email,
            name=actual_email.split("@")[0],
        )
        user = await user_service.create(user_data)
        await db.commit()
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide JWT token or email.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    email: Optional[str] = Query(None, description="User email for OAuth auth"),
    x_user_email: Optional[str] = Header(None, description="User email header"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    List sessions (conversations).

    - If project_id provided, list sessions for that project
    - Otherwise, list all user's sessions
    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)
    conversations, total = await service.list_by_user(
        user_id=current_user.id,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )

    return SessionListResponse(
        sessions=[SessionResponse.model_validate(c) for c in conversations],
        total=total,
    )


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    db: DBSession,
    session_data: SessionCreate,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None, description="User email header"),
):
    """
    Create a new session (conversation).

    Supports JWT or email-based authentication.
    """
    # Get email from session_data if provided
    email = getattr(session_data, 'email', None)
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)
    conversation = await service.create(
        user_id=current_user.id,
        session_data=session_data,
    )
    await db.commit()

    return SessionResponse.model_validate(conversation)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    email: Optional[str] = Query(None, description="User email for OAuth auth"),
    x_user_email: Optional[str] = Header(None, description="User email header"),
):
    """
    Get session (conversation) details.

    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)
    conversation = await service.get_by_id_and_user(
        conversation_id=session_id,
        user_id=current_user.id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse.model_validate(conversation)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    db: DBSession,
    session_data: SessionUpdate,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_email: Optional[str] = Header(None, description="User email header"),
):
    """
    Update session (conversation).

    Supports JWT or email-based authentication.
    """
    email = getattr(session_data, 'email', None)
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)
    conversation = await service.get_by_id_and_user(
        conversation_id=session_id,
        user_id=current_user.id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    conversation = await service.update(conversation, session_data)
    await db.commit()

    return SessionResponse.model_validate(conversation)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    email: Optional[str] = Query(None, description="User email for OAuth auth"),
    x_user_email: Optional[str] = Header(None, description="User email header"),
):
    """
    Delete session (conversation).

    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)
    conversation = await service.get_by_id_and_user(
        conversation_id=session_id,
        user_id=current_user.id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await service.delete(conversation)
    await db.commit()


@router.get("/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: str,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    email: Optional[str] = Query(None, description="User email for OAuth auth"),
    x_user_email: Optional[str] = Header(None, description="User email header"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    Get messages for a session (conversation).

    - Paginated results
    - Ordered by created_at ascending
    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(credentials, db, email, x_user_email)
    service = ConversationService(db)

    # Verify session ownership
    conversation = await service.get_by_id_and_user(
        conversation_id=session_id,
        user_id=current_user.id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages, total = await service.get_messages(
        conversation_id=session_id,
        skip=skip,
        limit=limit,
    )

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total,
    )
