"""Session service for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import Session
from app.models.message import Message, MessageRole
from app.schemas.session import SessionCreate, SessionUpdate, MessageCreate


class SessionService:
    """Service for session-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self,
        session_id: str,
        user_id: str,
    ) -> Optional[Session]:
        """Get session by ID and user."""
        result = await self.db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Session], int]:
        """List sessions by user."""
        query = select(Session).where(Session.user_id == user_id)

        if project_id:
            query = query.where(Session.project_id == project_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Session.updated_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def create(
        self,
        user_id: str,
        session_data: SessionCreate,
    ) -> Session:
        """Create a new session."""
        session = Session(
            user_id=user_id,
            title=session_data.title,
            project_id=session_data.project_id,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def update(
        self,
        session: Session,
        session_data: SessionUpdate,
    ) -> Session:
        """Update a session."""
        update_data = session_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(session, field, value)

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def delete(self, session: Session) -> None:
        """Delete a session."""
        await self.db.delete(session)
        await self.db.flush()

    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Message], int]:
        """Get messages for a session."""
        query = select(Message).where(Message.session_id == session_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Message.created_at.asc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        return messages, total

    async def add_message(
        self,
        session: Session,
        message_data: MessageCreate,
    ) -> Message:
        """Add a message to a session."""
        # Convert role string to enum
        role = MessageRole(message_data.role)

        message = Message(
            session_id=session.id,
            role=role,
            content=message_data.content,
            extra_data=message_data.extra_data,
        )
        self.db.add(message)

        # Update session
        session.message_count += 1
        session.last_message_at = datetime.now(timezone.utc)

        # Generate title from first user message if not set
        if not session.title and role == MessageRole.USER:
            session.title = message_data.content[:100] + (
                "..." if len(message_data.content) > 100 else ""
            )

        await self.db.flush()
        await self.db.refresh(message)
        return message
