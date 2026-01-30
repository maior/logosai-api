"""Session management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.session import (
    MessageListResponse,
    MessageResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services.session_service import SessionService

router = APIRouter()


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser,
    db: DBSession,
    project_id: Optional[str] = Query(None, description="Filter by project"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    List sessions.

    - If project_id provided, list sessions for that project
    - Otherwise, list all user's sessions
    Requires authentication.
    """
    service = SessionService(db)
    sessions, total = await service.list_by_user(
        user_email=current_user.email,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )

    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: CurrentUser,
    db: DBSession,
    session_data: SessionCreate,
):
    """
    Create a new session.

    Requires authentication.
    """
    service = SessionService(db)
    session = await service.create(
        user_email=current_user.email,
        session_data=session_data,
    )
    await db.commit()

    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get session details.

    Requires authentication and ownership.
    """
    service = SessionService(db)
    session = await service.get_by_id_and_user(
        session_id=session_id,
        user_email=current_user.email,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse.model_validate(session)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    current_user: CurrentUser,
    db: DBSession,
    session_data: SessionUpdate,
):
    """
    Update session.

    Requires authentication and ownership.
    """
    service = SessionService(db)
    session = await service.get_by_id_and_user(
        session_id=session_id,
        user_email=current_user.email,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session = await service.update(session, session_data)
    await db.commit()

    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete session.

    Requires authentication and ownership.
    """
    service = SessionService(db)
    session = await service.get_by_id_and_user(
        session_id=session_id,
        user_email=current_user.email,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await service.delete(session)
    await db.commit()


@router.get("/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: str,
    current_user: CurrentUser,
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    Get messages for a session.

    - Paginated results
    - Ordered by created_at ascending
    Requires authentication and ownership.
    """
    service = SessionService(db)

    # Verify session ownership
    session = await service.get_by_id_and_user(
        session_id=session_id,
        user_email=current_user.email,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages, total = await service.get_messages(
        session_id=session_id,
        skip=skip,
        limit=limit,
    )

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total,
    )
