"""Chat and streaming endpoints.

Provides website-compatible API responses for the chat system.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentUser, DBSession
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    RegenerateRequest,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/")
async def chat(
    current_user: CurrentUser,
    db: DBSession,
    request: ChatRequest,
) -> dict[str, Any]:
    """
    Send a chat message and get response.

    Returns website-compatible format:
    {
        "msg": "success",
        "code": 0,
        "data": {
            "result": "...",
            "usage_id": "...",
            "references": [...],
            ...
        }
    }

    - Synchronous response (waits for complete response)
    - Use /stream for real-time streaming
    Requires authentication.
    """
    service = ChatService(db)

    try:
        result = await service.process_chat(
            user_email=current_user.email,
            request=request,
        )

        # Return website-compatible format
        return {
            "msg": "success",
            "code": 0,
            "data": {
                "result": result.get("content", ""),
                "usage_id": result.get("message_id", ""),
                "reasoning": "",
                "category": result.get("agent_type", ""),
                "references": [],
                "pdf_names": [],
                "image_results": {},
                "agent_results": [{
                    "agent_id": result.get("agent_type", "default"),
                    "agent_name": result.get("agent_type", "Default Agent"),
                    "step_id": "step-1",
                    "result": result.get("content", ""),
                    "execution_time": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": 1.0,
                    "agentType": result.get("agent_type", ""),
                }],
                # Legacy fields
                "message_id": result.get("message_id", ""),
                "session_id": result.get("session_id", ""),
                "content": result.get("content", ""),
                "agent_type": result.get("agent_type"),
                "tokens_used": result.get("tokens_used"),
                "created_at": result.get("created_at").isoformat() if result.get("created_at") else None,
            },
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "msg": "error",
            "code": 500,
            "data": {
                "error": str(e),
                "result": "",
                "usage_id": "",
            },
        }


@router.post("/stream")
async def chat_stream(
    current_user: CurrentUser,
    db: DBSession,
    request: ChatRequest,
):
    """
    Send a chat message and get streaming response.

    Returns Server-Sent Events (SSE) stream with:
    - ontology_init: Query analysis started
    - agents_selected: Agents selected for task
    - workflow_plan_created: Execution plan created
    - agent_started: Agent execution started
    - agent_progress: Agent progress update
    - agent_completed: Agent completed
    - final_result: Final response
    - message_saved: Message saved to database
    - error: Error occurred

    Requires authentication.
    """
    service = ChatService(db)

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events."""
        try:
            async for event in service.stream_chat(
                user_email=current_user.email,
                request=request,
            ):
                # Format event for SSE
                yield {
                    "event": event.get("event", "message"),
                    "data": json.dumps(event.get("data", {}), ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "error_code": "STREAM_ERROR",
                    "message": str(e),
                }, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/regenerate", response_model=ChatResponse)
async def regenerate_response(
    current_user: CurrentUser,
    db: DBSession,
    request: RegenerateRequest,
):
    """
    Regenerate a response for a message.

    Requires authentication.
    """
    # TODO: Implement regeneration logic
    # 1. Get the original user message
    # 2. Delete the assistant response
    # 3. Re-process through ACP server
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Regeneration not implemented yet",
    )


@router.get("/health")
async def chat_health():
    """
    Check chat service and ACP server health.

    Public endpoint for monitoring.
    """
    from app.services.acp_client import get_acp_client

    acp_client = get_acp_client()
    acp_healthy = await acp_client.health_check()

    return {
        "chat_service": "healthy",
        "acp_server": "healthy" if acp_healthy else "unavailable",
        "acp_server_url": acp_client.base_url,
    }
