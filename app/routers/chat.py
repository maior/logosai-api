"""Chat and streaming endpoints.

Provides website-compatible API responses for the chat system.
Supports both JWT and email-based authentication.
Uses logosus schema for user management and conversations.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DBSession
from app.core.security import verify_token
from app.database import get_db
from app.models.logosus.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    RegenerateRequest,
)
from app.middleware.response_normalizer import normalize_final_result, normalize_error_response, normalize_sync_response
from app.middleware.response_middleware import normalized_event_generator
from app.services.chat_service import ChatService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional HTTP Bearer
security = HTTPBearer(auto_error=False)


async def get_user_from_request(
    request: ChatRequest,
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
) -> User:
    """
    Get user from JWT token or email in request body.

    Uses logosus schema where users have UUID as primary key.

    Priority:
    1. JWT Bearer token (if provided)
    2. Email in request body (for OAuth users)
    """
    user_service = UserService(db)

    # Try JWT auth first
    if credentials:
        payload = verify_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            user_email = payload.get("email") or payload.get("sub")
            user = await user_service.get_by_email(user_email)
            if user:
                return user

    # Fall back to email in request body
    if request.email:
        user = await user_service.get_by_email(request.email)
        if user:
            return user

        # Auto-create user if not exists (for OAuth)
        from app.schemas.user import UserCreate
        user_data = UserCreate(
            email=request.email,
            name=request.email.split("@")[0],
        )
        user = await user_service.create(user_data)
        await db.commit()  # Commit to ensure user exists for conversation creation
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide JWT token or email.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/")
async def chat(
    request: ChatRequest,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
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
    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(request, credentials, db)
    service = ChatService(db)

    try:
        result = await service.process_chat(
            user_id=current_user.id,
            request=request,
            user_email=current_user.email,  # Pass email for ACP server compatibility
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
        error_response = normalize_error_response(e)
        return {
            "msg": "error",
            "code": 500,
            "data": error_response.get("data", {}).get("data", {
                "result": "요청을 처리하는 중 오류가 발생했습니다.",
                "usage_id": "",
            }),
        }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
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

    Supports JWT or email-based authentication.
    """
    current_user = await get_user_from_request(request, credentials, db)
    service = ChatService(db)

    async def raw_event_generator() -> AsyncGenerator[dict, None]:
        """Generate raw SSE events from orchestrator."""
        async for event in service.stream_chat(
            user_id=current_user.id,
            request=request,
            user_email=current_user.email,  # Pass email for ACP server compatibility
        ):
            yield event

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate normalized SSE events."""
        try:
            async for event in normalized_event_generator(raw_event_generator()):
                # Format event for SSE
                event_type = event.get("event", "message")

                # data 필드에 전체 이벤트 정보 포함
                data_payload = event.get("data", {})
                if isinstance(data_payload, dict):
                    # 최상위 필드들을 data에도 복사 (프론트엔드 호환)
                    data_payload = {
                        **data_payload,
                        "event": event_type,
                        "message": event.get("message", data_payload.get("message", "")),
                        "stage": event.get("stage", ""),
                        "progress": event.get("progress", data_payload.get("progress")),
                    }
                    # agents 정보가 있으면 포함
                    if "agents" in event:
                        data_payload["agents"] = event["agents"]
                    if "selected_agents" in event:
                        data_payload["selected_agents"] = event["selected_agents"]
                    if "workflow_visualization" in event:
                        data_payload["workflow_visualization"] = event["workflow_visualization"]
                    if "total_stages" in event:
                        data_payload["total_stages"] = event["total_stages"]

                yield {
                    "event": event_type,
                    "data": json.dumps(data_payload, ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_event = normalize_error_response(e)
            yield {
                "event": "final_result",
                "data": json.dumps(error_event.get("data", {}), ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/regenerate", response_model=ChatResponse)
async def regenerate_response(
    request: RegenerateRequest,
    db: DBSession,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
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
