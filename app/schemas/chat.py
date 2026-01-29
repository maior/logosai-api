"""Chat schemas for request/response validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request schema."""
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    project_id: Optional[str] = None

    # Optional context
    context: Optional[dict[str, Any]] = None

    # Agent selection hints
    preferred_agents: Optional[list[str]] = None
    exclude_agents: Optional[list[str]] = None


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message_id: str
    session_id: str
    content: str
    agent_type: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime


class RegenerateRequest(BaseModel):
    """Regenerate response request."""
    message_id: str
    session_id: str


# SSE Event Types
class BaseStreamEvent(BaseModel):
    """Base SSE stream event."""
    event: str
    timestamp: datetime = Field(default_factory=datetime.now)


class OntologyInitEvent(BaseStreamEvent):
    """Ontology initialization event."""
    event: str = "ontology_init"
    message: str
    stage: str
    progress: int


class AgentsSelectedEvent(BaseStreamEvent):
    """Agents selected event."""
    event: str = "agents_selected"
    message: str
    agents: list[dict[str, str]]
    progress: int


class WorkflowPlanEvent(BaseStreamEvent):
    """Workflow plan created event."""
    event: str = "workflow_plan_created"
    message: str
    plan: dict[str, Any]
    progress: int


class AgentStartedEvent(BaseStreamEvent):
    """Agent execution started event."""
    event: str = "agent_started"
    agent_id: str
    agent_name: str
    task: str
    progress: int


class AgentProgressEvent(BaseStreamEvent):
    """Agent progress update event."""
    event: str = "agent_progress"
    agent_id: str
    message: str
    partial_result: Optional[str] = None
    progress: int


class AgentCompletedEvent(BaseStreamEvent):
    """Agent completed event."""
    event: str = "agent_completed"
    agent_id: str
    agent_name: str
    result: Optional[str] = None
    tokens_used: Optional[int] = None
    progress: int


class FinalResultEvent(BaseStreamEvent):
    """Final result event."""
    event: str = "final_result"
    message_id: str
    session_id: str
    content: str
    agent_type: Optional[str] = None
    tokens_used: Optional[int] = None
    progress: int = 100


class ErrorEvent(BaseStreamEvent):
    """Error event."""
    event: str = "error"
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None
