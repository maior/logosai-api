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
        user_email: str,
        request: ChatRequest,
    ) -> dict[str, Any]:
        """
        Process chat request synchronously.

        Args:
            user_email: User email (used as primary identifier)
            request: Chat request

        Returns:
            Chat response
        """
        # Get or create session
        session = await self._get_or_create_session(
            user_email=user_email,
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
        user_email: str,
        request: ChatRequest,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process chat request with streaming.

        Args:
            user_email: User email (used as primary identifier)
            request: Chat request

        Yields:
            SSE events
        """
        # Get or create session
        session = await self._get_or_create_session(
            user_email=user_email,
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

        # Emit initial events (website-compatible)
        yield {
            "event": "initialization",  # Website compatible
            "data": {
                "message": "시스템 초기화 중...",
                "stage": "initialization",
                "session_id": session.id,
                "progress": 5,
            },
        }

        yield {
            "event": "ontology_init",
            "data": {
                "message": "온톨로지 시스템으로 쿼리 분석 중...",
                "stage": "ontology_initialization",
                "session_id": session.id,
                "progress": 10,
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
                # ACP server returns triple-nested structure:
                # event.data.data.data.result (SSE wrapper -> event wrapper -> response wrapper -> result)
                # Level 1: event.data = {"event": "final_result", "data": {...}}
                # Level 2: data.data = {"code": 0, "msg": "success", "data": {...}}
                # Level 3: inner.data = {"result": "...", "agent_results": [...]}

                level1 = data.get("data", data)  # Handle both wrapped and unwrapped
                level2 = level1.get("data", level1) if isinstance(level1, dict) else {}

                final_content = level2.get("result", "") or data.get("content", "")

                # Extract agent type from agent_results
                agent_results = level2.get("agent_results", [])
                if agent_results:
                    agent_type = agent_results[0].get("agent_id")
                else:
                    agent_type = data.get("agent_type")

                tokens_used = data.get("tokens_used")

                logger.info(f"Captured final_result: content_length={len(final_content)}, agent_type={agent_type}")

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
        Events are website-compatible.
        """
        import asyncio

        # Agent discovery event (website compatible)
        yield {
            "event": "agent_discovery",
            "data": {
                "message": "사용 가능한 에이전트 검색 중...",
                "progress": 15,
            },
        }
        await asyncio.sleep(0.05)

        # Agents found/selected event
        yield {
            "event": "agents_selected",
            "data": {
                "message": "에이전트 선택 완료",
                "agents": [
                    {
                        "id": "fallback-agent",
                        "name": "Fallback Agent",
                        "type": "fallback",
                        "status": "ready",
                        "description": "ACP 서버 미연결 시 대체 에이전트",
                    },
                ],
                "progress": 25,
            },
        }
        await asyncio.sleep(0.05)

        # System selection event
        yield {
            "event": "system_selected",
            "data": {
                "message": "시스템 선택 완료",
                "system_type": "FALLBACK",
                "progress": 30,
            },
        }
        await asyncio.sleep(0.05)

        yield {
            "event": "workflow_plan_created",
            "data": {
                "message": "워크플로우 계획 생성됨",
                "plan": {
                    "visualization": "",
                    "steps": [
                        {
                            "step_id": "step-1",
                            "agent_id": "fallback-agent",
                            "description": "응답 생성",
                            "depends_on": [],
                        },
                    ],
                    "execution_order": ["step-1"],
                    "reasoning": "ACP 서버 미연결로 대체 응답 생성",
                    "estimated_time": 1,
                },
                "progress": 40,
            },
        }
        await asyncio.sleep(0.05)

        # Step executing event (website compatible)
        yield {
            "event": "step_executing",
            "data": {
                "message": "에이전트 실행 중...",
                "step_id": "step-1",
                "agent_id": "fallback-agent",
                "progress": 50,
            },
        }

        yield {
            "event": "agent_started",
            "data": {
                "agent_id": "fallback-agent",
                "agent_name": "Fallback Agent",
                "task": "응답 생성",
                "progress": 55,
            },
        }
        await asyncio.sleep(0.1)

        # Content delta events (website compatible - streaming text)
        fallback_content = (
            f"ACP 서버에 연결할 수 없어 대체 응답을 제공합니다.\n\n"
            f"질문: {query}\n\n"
            f"ACP 서버가 다시 시작되면 완전한 에이전트 기반 응답을 받을 수 있습니다."
        )

        # Simulate content streaming
        words = fallback_content.split()
        accumulated = ""
        for i, word in enumerate(words):
            accumulated += word + " "
            if i % 5 == 0:  # Send every 5 words
                yield {
                    "event": "content_delta",
                    "data": {
                        "delta": word + " ",
                        "accumulated_text": accumulated.strip(),
                        "progress": 60 + int((i / len(words)) * 20),
                    },
                }
                await asyncio.sleep(0.02)

        # Step completed event
        yield {
            "event": "step_completed",
            "data": {
                "step_id": "step-1",
                "agent_id": "fallback-agent",
                "agent_name": "Fallback Agent",
                "completed_count": 1,
                "total_count": 1,
                "progress": 85,
            },
        }

        yield {
            "event": "agent_completed",
            "data": {
                "agent_id": "fallback-agent",
                "agent_name": "Fallback Agent",
                "result": fallback_content,
                "progress": 90,
            },
        }

        # Integration started event
        yield {
            "event": "integration_started",
            "data": {
                "message": "결과 통합 중...",
                "progress": 92,
            },
        }
        await asyncio.sleep(0.05)

        # Save the fallback response
        message = await self._save_message(
            session=session,
            role=MessageRole.ASSISTANT,
            content=fallback_content,
            agent_type="fallback",
        )
        await self.db.commit()

        # Final result with all website-expected fields
        yield {
            "event": "final_result",
            "data": {
                # Website-compatible format (ChatResponse.data)
                "result": fallback_content,
                "usage_id": message.id,
                "reasoning": "ACP 서버 미연결로 인한 대체 응답",
                "category": "fallback",
                "references": [],
                "pdf_names": [],
                "image_results": {},
                "graph_data": None,
                "knowledge_graph_visualization": None,
                "evaluation_data": None,
                "rl_metrics": None,
                "shopping_results": None,
                "pdf_info": [],
                "ontology_insights": None,
                "execution_stats": {
                    "total_time": 0.5,
                    "agent_count": 1,
                },
                "execution_plan": {
                    "steps": ["fallback-agent"],
                },
                "agent_info": {
                    "fallback-agent": {
                        "name": "Fallback Agent",
                        "type": "fallback",
                    },
                },
                "agent_results": [{
                    "agent_id": "fallback-agent",
                    "agent_name": "Fallback Agent",
                    "step_id": "step-1",
                    "result": fallback_content,
                    "execution_time": 0.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": 0.5,
                    "hasArtifacts": False,
                    "agentType": "fallback",
                }],
                # Legacy fields for backward compatibility
                "message_id": message.id,
                "session_id": session.id,
                "content": fallback_content,
                "agent_type": "fallback",
                "progress": 100,
            },
        }

        # Completion event (website compatible alias)
        yield {
            "event": "completion",
            "data": {
                "message": "처리 완료",
                "progress": 100,
            },
        }

    async def _get_or_create_session(
        self,
        user_email: str,
        session_id: Optional[str],
        project_id: Optional[str],
    ) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = await self.session_service.get_by_id_and_user(
                session_id=session_id,
                user_email=user_email,
            )
            if session:
                return session

        # Create new session
        from app.schemas.session import SessionCreate
        session_data = SessionCreate(project_id=project_id)
        return await self.session_service.create(
            user_email=user_email,
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
            role=role.value,  # Convert enum to string value for DB
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
