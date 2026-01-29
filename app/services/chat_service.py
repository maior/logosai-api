"""Chat service for handling chat operations."""

import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole
from app.models.session import Session
from app.schemas.chat import ChatRequest
from app.services.acp_client import ACPClient, ACPClientError, get_acp_client
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations with streaming support."""

    def __init__(
        self,
        db: AsyncSession,
        acp_client: Optional[ACPClient] = None,
    ):
        self.db = db
        self.acp_client = acp_client or get_acp_client()
        self.session_service = SessionService(db)

    async def process_chat(
        self,
        user_id: str,
        user_email: str,
        request: ChatRequest,
    ) -> dict[str, Any]:
        """
        Process chat request synchronously.

        Args:
            user_id: User ID
            user_email: User email
            request: Chat request

        Returns:
            Chat response
        """
        # Get or create session
        session = await self._get_or_create_session(
            user_id=user_id,
            session_id=request.session_id,
            project_id=request.project_id,
        )

        # Save user message
        user_message = await self._save_message(
            session=session,
            role=MessageRole.USER,
            content=request.query,
        )

        try:
            # Process through ACP server
            response = await self.acp_client.process_query(
                query=request.query,
                user_email=user_email,
                session_id=session.id,
                project_id=request.project_id,
                context=request.context,
            )

            # Save assistant message
            assistant_message = await self._save_message(
                session=session,
                role=MessageRole.ASSISTANT,
                content=response.get("content", ""),
                agent_type=response.get("agent_type"),
                tokens_used=response.get("tokens_used"),
                extra_data=response.get("metadata"),
            )

            await self.db.commit()

            return {
                "message_id": assistant_message.id,
                "session_id": session.id,
                "content": response.get("content", ""),
                "agent_type": response.get("agent_type"),
                "tokens_used": response.get("tokens_used"),
                "created_at": assistant_message.created_at,
            }

        except ACPClientError as e:
            logger.error(f"ACP error: {e}")
            raise

    async def stream_chat(
        self,
        user_id: str,
        user_email: str,
        request: ChatRequest,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process chat request with streaming.

        Args:
            user_id: User ID
            user_email: User email
            request: Chat request

        Yields:
            SSE events
        """
        # Get or create session
        session = await self._get_or_create_session(
            user_id=user_id,
            session_id=request.session_id,
            project_id=request.project_id,
        )

        # Save user message
        user_message = await self._save_message(
            session=session,
            role=MessageRole.USER,
            content=request.query,
        )
        await self.db.commit()

        # Emit initial event
        yield {
            "event": "ontology_init",
            "data": {
                "message": "온톨로지 시스템으로 쿼리 분석 중...",
                "stage": "ontology_initialization",
                "session_id": session.id,
                "progress": 5,
            },
        }

        # Check ACP server health
        is_healthy = await self.acp_client.health_check()

        if not is_healthy:
            # Fallback to mock streaming if ACP is not available
            logger.warning("ACP server not available, using fallback")
            async for event in self._fallback_stream(session, request.query):
                yield event
            return

        # Stream from ACP server
        final_content = ""
        agent_type = None
        tokens_used = None

        async for event in self.acp_client.stream_query(
            query=request.query,
            user_email=user_email,
            session_id=session.id,
            project_id=request.project_id,
            context=request.context,
        ):
            # Pass through events
            yield event

            # Capture final result
            if event.get("event") == "final_result":
                data = event.get("data", {})
                final_content = data.get("content", "")
                agent_type = data.get("agent_type")
                tokens_used = data.get("tokens_used")

        # Save assistant message if we got a result
        if final_content:
            assistant_message = await self._save_message(
                session=session,
                role=MessageRole.ASSISTANT,
                content=final_content,
                agent_type=agent_type,
                tokens_used=tokens_used,
            )
            await self.db.commit()

            # Send completion event
            yield {
                "event": "message_saved",
                "data": {
                    "message_id": assistant_message.id,
                    "session_id": session.id,
                },
            }

    async def _fallback_stream(
        self,
        session: Session,
        query: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fallback streaming when ACP server is not available.

        This provides a graceful degradation with simulated events.
        """
        import asyncio

        # Simulate processing stages
        yield {
            "event": "agents_selected",
            "data": {
                "message": "에이전트 선택 완료",
                "agents": [
                    {"id": "fallback-agent", "name": "Fallback Agent"},
                ],
                "progress": 30,
            },
        }
        await asyncio.sleep(0.1)

        yield {
            "event": "workflow_plan_created",
            "data": {
                "message": "워크플로우 계획 생성됨",
                "plan": {
                    "steps": [
                        {"agent": "Fallback Agent", "task": "응답 생성"},
                    ],
                },
                "progress": 50,
            },
        }
        await asyncio.sleep(0.1)

        yield {
            "event": "agent_started",
            "data": {
                "agent_id": "fallback-agent",
                "agent_name": "Fallback Agent",
                "task": "응답 생성",
                "progress": 60,
            },
        }
        await asyncio.sleep(0.1)

        # Generate fallback response
        fallback_content = (
            f"ACP 서버에 연결할 수 없어 대체 응답을 제공합니다.\n\n"
            f"질문: {query}\n\n"
            f"ACP 서버가 다시 시작되면 완전한 에이전트 기반 응답을 받을 수 있습니다."
        )

        yield {
            "event": "agent_completed",
            "data": {
                "agent_id": "fallback-agent",
                "agent_name": "Fallback Agent",
                "result": fallback_content,
                "progress": 90,
            },
        }

        # Save the fallback response
        message = await self._save_message(
            session=session,
            role=MessageRole.ASSISTANT,
            content=fallback_content,
            agent_type="fallback",
        )
        await self.db.commit()

        yield {
            "event": "final_result",
            "data": {
                "message_id": message.id,
                "session_id": session.id,
                "content": fallback_content,
                "agent_type": "fallback",
                "progress": 100,
            },
        }

    async def _get_or_create_session(
        self,
        user_id: str,
        session_id: Optional[str],
        project_id: Optional[str],
    ) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = await self.session_service.get_by_id_and_user(
                session_id=session_id,
                user_id=user_id,
            )
            if session:
                return session

        # Create new session
        from app.schemas.session import SessionCreate
        session_data = SessionCreate(project_id=project_id)
        return await self.session_service.create(
            user_id=user_id,
            session_data=session_data,
        )

    async def _save_message(
        self,
        session: Session,
        role: MessageRole,
        content: str,
        agent_type: Optional[str] = None,
        tokens_used: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> Message:
        """Save a message to the database."""
        message = Message(
            id=str(uuid4()),
            session_id=session.id,
            role=role,
            content=content,
            agent_type=agent_type,
            tokens_used=tokens_used,
            extra_data=extra_data,
        )
        self.db.add(message)

        # Update session
        session.message_count += 1
        session.last_message_at = datetime.now(timezone.utc)

        # Set title from first user message
        if not session.title and role == MessageRole.USER:
            session.title = content[:100] + ("..." if len(content) > 100 else "")

        await self.db.flush()
        await self.db.refresh(message)
        return message
