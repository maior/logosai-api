"""Conversation service for chat operations.

Uses logosus schema for conversation management (logos_api independent).
Note: In logosus, "Conversation" is for chat, "Session" is for authentication.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.logosus.conversation import Conversation, Message
from app.models.logosus.user import User
from app.schemas.session import SessionCreate, SessionUpdate, MessageCreate


class ConversationService:
    """Service for conversation-related database operations.

    Uses logosus schema where:
    - Conversation uses UUID as primary key
    - Conversation.user_id references logosus.users.id (UUID)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Optional[Conversation]:
        """Get conversation by ID and user ID."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Conversation], int]:
        """List conversations by user ID."""
        query = select(Conversation).where(Conversation.user_id == user_id)

        if project_id:
            query = query.where(Conversation.project_id == project_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Conversation.updated_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        conversations = list(result.scalars().all())

        return conversations, total

    async def create(
        self,
        user_id: str,
        session_data: SessionCreate,
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            user_id=user_id,
            title=session_data.title,
            project_id=session_data.project_id,
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def update(
        self,
        conversation: Conversation,
        session_data: SessionUpdate,
    ) -> Conversation:
        """Update a conversation."""
        update_data = session_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(conversation, field):
                setattr(conversation, field, value)

        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def delete(self, conversation: Conversation) -> None:
        """Delete a conversation."""
        await self.db.delete(conversation)
        await self.db.flush()

    async def get_messages(
        self,
        conversation_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Message], int]:
        """Get messages for a conversation."""
        query = select(Message).where(Message.conversation_id == conversation_id)

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
        conversation: Conversation,
        role: str,
        content: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        agent_metadata: Optional[dict] = None,
        references: Optional[dict] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            agent_name=agent_name,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            agent_metadata=agent_metadata,
            references=references,
        )
        self.db.add(message)

        # Update conversation stats
        conversation.message_count += 1
        if tokens_input:
            conversation.total_tokens += tokens_input
        if tokens_output:
            conversation.total_tokens += tokens_output

        # Generate title from first user message if not set
        if not conversation.title and role == "user":
            conversation.title = content[:100] + ("..." if len(content) > 100 else "")

        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def add_feedback(
        self,
        message: Message,
        score: float,
        text: Optional[str] = None,
    ) -> Message:
        """Add feedback to a message."""
        message.feedback_score = score
        message.feedback_text = text
        await self.db.flush()
        await self.db.refresh(message)
        return message


# Alias for backward compatibility with session_service imports
SessionService = ConversationService
