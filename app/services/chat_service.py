"""Chat service for handling chat operations.

Uses logosus schema for conversation and message storage (logos_api independent).
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logosus.conversation import Conversation, Message
from app.schemas.chat import ChatRequest
from app.services.acp_client import ACPClient, ACPClientError, get_acp_client
from app.services.orchestrator_service import OrchestratorService, get_orchestrator_service
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

# 환경 변수로 Orchestrator 사용 여부 제어
USE_ORCHESTRATOR = os.getenv("USE_ORCHESTRATOR", "true").lower() == "true"


class ChatService:
    """Service for chat operations with streaming support.

    Uses logosus.Conversation for chat sessions and logosus.Message for messages.
    """

    def __init__(
        self,
        db: AsyncSession,
        acp_client: Optional[ACPClient] = None,
        orchestrator_service: Optional[OrchestratorService] = None,
    ):
        self.db = db
        self.acp_client = acp_client or get_acp_client()
        self.orchestrator_service = orchestrator_service or get_orchestrator_service()
        self.conversation_service = ConversationService(db)

    async def process_chat(
        self,
        user_id: str,
        request: ChatRequest,
        user_email: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process chat request synchronously.

        Args:
            user_id: User UUID (logosus.users.id)
            request: Chat request
            user_email: Optional user email for ACP server

        Returns:
            Chat response
        """
        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id=user_id,
            conversation_id=request.session_id,
            project_id=request.project_id,
        )

        # Save user message
        user_message = await self._save_message(
            conversation=conversation,
            role="user",
            content=request.query,
        )

        try:
            # Process through ACP server (uses email for compatibility)
            response = await self.acp_client.process_query(
                query=request.query,
                user_email=user_email or user_id,  # Fallback to user_id
                session_id=conversation.id,
                project_id=request.project_id,
                context=request.context,
            )

            # Save assistant message
            assistant_message = await self._save_message(
                conversation=conversation,
                role="assistant",
                content=response.get("content", ""),
                agent_name=response.get("agent_type"),
                tokens_output=response.get("tokens_used"),
                agent_metadata=response.get("metadata"),
            )

            await self.db.commit()

            return {
                "message_id": assistant_message.id,
                "session_id": conversation.id,
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
        request: ChatRequest,
        user_email: Optional[str] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process chat request with streaming.

        USE_ORCHESTRATOR=true 일 때 WorkflowOrchestrator 사용 (Django와 동일한 기능)
        USE_ORCHESTRATOR=false 일 때 직접 ACP 서버 호출 (레거시)

        Args:
            user_id: User UUID (logosus.users.id)
            request: Chat request
            user_email: Optional user email for ACP server

        Yields:
            SSE events
        """
        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id=user_id,
            conversation_id=request.session_id,
            project_id=request.project_id,
        )

        # Save user message
        user_message = await self._save_message(
            conversation=conversation,
            role="user",
            content=request.query,
        )
        await self.db.commit()

        # Load conversation history for context continuity
        enriched_context = {**(request.context or {})}
        try:
            conv_service = ConversationService(self.db)
            recent_messages, _ = await conv_service.get_messages(
                conversation_id=conversation.id,
                skip=0,
                limit=20,  # Last 20 messages (10 turns)
            )
            if len(recent_messages) > 1:  # More than just the current user message
                history_lines = []
                for msg in recent_messages[:-1]:  # Exclude the just-saved user message
                    role = "User" if msg.role == "user" else "Assistant"
                    content = msg.content[:500] if msg.content else ""
                    history_lines.append(f"{role}: {content}")
                if history_lines:
                    enriched_context["conversation_history"] = "\n".join(history_lines[-10:])
                    logger.info(f"💬 Loaded {len(history_lines)} messages as conversation history")
        except Exception as e:
            logger.warning(f"Conversation history loading failed: {e}")

        # Load user memories for context injection
        try:
            from app.services.memory_service import MemoryService
            memory_service = MemoryService(self.db)
            user_memories_text = await memory_service.load_memories_for_context(user_id)
            if user_memories_text:
                enriched_context["user_memories"] = user_memories_text
                logger.info(f"Loaded user memories for context injection ({len(user_memories_text)} chars)")
        except Exception as e:
            logger.debug(f"Memory loading skipped: {e}")

        # Replace request context with enriched version
        request.context = enriched_context if enriched_context else request.context

        # Emit memory_context event if memories were loaded
        if enriched_context.get("user_memories"):
            mem_text = enriched_context["user_memories"]
            memory_count = mem_text.count("\n- ")
            yield {
                "event": "memory_context",
                "data": {
                    "memory_count": memory_count,
                    "message": f"Loaded {memory_count} user memories",
                },
            }

        # Emit initial events (website-compatible)
        yield {
            "event": "initialization",
            "data": {
                "message": "시스템 초기화 중...",
                "stage": "initialization",
                "session_id": conversation.id,
                "progress": 5,
            },
        }

        # USE_ORCHESTRATOR=true 일 때 WorkflowOrchestrator 사용
        if USE_ORCHESTRATOR:
            logger.info("🚀 Using WorkflowOrchestrator for multi-agent streaming")
            async for event in self._stream_with_orchestrator(conversation, request, user_email or user_id):
                yield event
            return

        # 레거시: 직접 ACP 서버 호출 (DataTransformer 없음)
        logger.info("⚠️ Using direct ACP streaming (no DataTransformer)")
        async for event in self._stream_direct_acp(conversation, request, user_email or user_id):
            yield event

    async def _stream_with_orchestrator(
        self,
        conversation: Conversation,
        request: ChatRequest,
        user_email: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        WorkflowOrchestrator를 사용한 멀티 에이전트 스트리밍.

        Django의 multi_agent_streaming.py와 동일한 기능:
        - UnifiedQueryProcessor로 쿼리 분석
        - WorkflowOrchestrator로 워크플로우 계획 생성
        - DataTransformer로 에이전트 간 데이터 변환
        - SSE 이벤트 스트리밍
        """
        final_content = ""
        agent_type = None
        agent_results = []
        knowledge_graph = None

        async for event in self.orchestrator_service.stream_with_orchestrator(
            query=request.query,
            user_email=user_email,
            session_id=conversation.id,
            project_id=request.project_id,
            context=request.context,
        ):
            # Pass through events
            yield event

            # Capture final result
            event_type = event.get("event", "")
            if event_type == "final_result":
                data = event.get("data", {})

                # 결과 추출 (다중 레벨 중첩 처리)
                level1 = data.get("data", data)
                level2 = level1.get("data", level1) if isinstance(level1, dict) else {}

                final_content = (
                    level2.get("result", "") or
                    data.get("result", "") or
                    data.get("content", "")
                )

                # 에이전트 결과 추출
                agent_results = level2.get("agent_results", data.get("agent_results", []))
                if agent_results:
                    agent_type = agent_results[0].get("agent_id")

                # 이미지/링크가 포함된 리치 콘텐츠가 agent_results에 있으면
                # 오케스트레이터 요약 대신 원본 에이전트 결과를 사용
                if agent_results:
                    best_rich = None
                    best_len = 0
                    for ar in agent_results:
                        ac = ar.get("result", "")
                        if isinstance(ac, dict):
                            ac = ac.get("content", ac.get("answer", ""))
                        if isinstance(ac, str) and ac and ("![" in ac or "<img" in ac or "<!--SHOP_DATA:" in ac):
                            if len(ac) > best_len:
                                best_rich = ac
                                best_len = len(ac)
                    if best_rich and best_len > len(final_content):
                        logger.info(
                            f"Using rich agent content ({best_len} chars) "
                            f"instead of summary ({len(final_content)} chars)"
                        )
                        final_content = best_rich

                # Knowledge Graph 추출
                knowledge_graph = (
                    level2.get("knowledge_graph_visualization") or
                    level1.get("knowledge_graph_visualization") or
                    data.get("knowledge_graph_visualization")
                )

                logger.info(f"Captured final_result: content_length={len(final_content)}, agents={len(agent_results)}, has_kg={knowledge_graph is not None}")

        # Save assistant message
        if final_content:
            agent_metadata = {}
            if agent_results:
                agent_metadata["agent_results"] = agent_results
            if knowledge_graph:
                agent_metadata["knowledge_graph"] = knowledge_graph

            assistant_message = await self._save_message(
                conversation=conversation,
                role="assistant",
                content=final_content,
                agent_name=agent_type,
                agent_metadata=agent_metadata if agent_metadata else None,
            )
            await self.db.commit()

            yield {
                "event": "message_saved",
                "data": {
                    "message_id": assistant_message.id,
                    "session_id": conversation.id,
                },
            }

            # Background memory extraction (non-blocking)
            asyncio.create_task(
                self._extract_memories_background(
                    user_id=conversation.user_id,
                    conversation_id=conversation.id,
                    query=request.query,
                    response=final_content,
                )
            )

    async def _extract_memories_background(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        response: str,
    ) -> None:
        """Extract user memories from conversation in background.

        Uses an independent DB session to avoid interfering with the
        main request session.
        """
        try:
            from app.database import get_db_context
            from app.services.memory_service import MemoryService

            async with get_db_context() as db:
                memory_service = MemoryService(db)
                new_memories = await memory_service.extract_memories_from_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    messages=[
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response},
                    ],
                )
                if new_memories:
                    logger.info(
                        f"Background: extracted {len(new_memories)} memories "
                        f"for user {user_id[:8]}..."
                    )
        except Exception as e:
            logger.warning(f"Memory extraction failed (non-critical): {e}")

    async def _stream_direct_acp(
        self,
        conversation: Conversation,
        request: ChatRequest,
        user_email: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        레거시: 직접 ACP 서버 호출.

        주의: DataTransformer가 작동하지 않으므로 멀티 에이전트 간 데이터 전달 불가.
        """
        yield {
            "event": "ontology_init",
            "data": {
                "message": "온톨로지 시스템으로 쿼리 분석 중...",
                "stage": "ontology_initialization",
                "session_id": conversation.id,
                "progress": 10,
            },
        }

        # Check ACP server health
        is_healthy = await self.acp_client.health_check()

        if not is_healthy:
            logger.warning("ACP server not available, using fallback")
            async for event in self._fallback_stream(conversation, request.query):
                yield event
            return

        # Stream from ACP server
        final_content = ""
        agent_type = None
        tokens_used = None
        agent_results = []
        knowledge_graph = None

        async for event in self.acp_client.stream_query(
            query=request.query,
            user_email=user_email,
            session_id=conversation.id,
            project_id=request.project_id,
            context=request.context,
        ):
            yield event

            if event.get("event") == "final_result":
                data = event.get("data", {})
                level1 = data.get("data", data)
                level2 = level1.get("data", level1) if isinstance(level1, dict) else {}

                final_content = level2.get("result", "") or data.get("content", "")

                agent_results = level2.get("agent_results", [])
                if agent_results:
                    agent_type = agent_results[0].get("agent_id")
                else:
                    agent_type = data.get("agent_type")

                tokens_used = data.get("tokens_used")

                # Knowledge Graph 추출
                knowledge_graph = (
                    level2.get("knowledge_graph_visualization") or
                    level1.get("knowledge_graph_visualization") or
                    data.get("knowledge_graph_visualization")
                )

                logger.info(f"Captured final_result: content_length={len(final_content)}, agent_type={agent_type}, has_kg={knowledge_graph is not None}")

        if final_content:
            agent_metadata = {}
            if agent_results:
                agent_metadata["agent_results"] = agent_results
            if knowledge_graph:
                agent_metadata["knowledge_graph"] = knowledge_graph

            assistant_message = await self._save_message(
                conversation=conversation,
                role="assistant",
                content=final_content,
                agent_name=agent_type,
                tokens_output=tokens_used,
                agent_metadata=agent_metadata if agent_metadata else None,
            )
            await self.db.commit()

            yield {
                "event": "message_saved",
                "data": {
                    "message_id": assistant_message.id,
                    "session_id": conversation.id,
                },
            }

    async def _fallback_stream(
        self,
        conversation: Conversation,
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
            conversation=conversation,
            role="assistant",
            content=fallback_content,
            agent_name="fallback",
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
                "session_id": conversation.id,
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

    async def _get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        project_id: Optional[str],
    ) -> Conversation:
        """Get existing conversation or create new one."""
        if conversation_id:
            conversation = await self.conversation_service.get_by_id_and_user(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            if conversation:
                return conversation

        # Create new conversation
        from app.schemas.session import SessionCreate
        session_data = SessionCreate(project_id=project_id)
        return await self.conversation_service.create(
            user_id=user_id,
            session_data=session_data,
        )

    async def _save_message(
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
        """Save a message to the database."""
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

        # Set title from first user message
        if not conversation.title and role == "user":
            conversation.title = content[:100] + ("..." if len(content) > 100 else "")

        await self.db.flush()
        await self.db.refresh(message)
        return message
