"""Chat schemas for request/response validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request schema."""
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    project_id: Optional[str] = None

    # Email-based authentication (for OAuth users)
    email: Optional[str] = None

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


class AgentResult(BaseModel):
    """Individual agent result for website compatibility."""
    agent_id: str
    agent_name: str
    step_id: str
    result: Any
    execution_time: float
    timestamp: str
    confidence: Optional[float] = None
    hasArtifacts: Optional[bool] = False
    agentType: Optional[str] = None


class FinalResultEvent(BaseStreamEvent):
    """Final result event - Website compatible format."""
    event: str = "final_result"

    # Website-expected fields (primary)
    result: str  # Main response text
    usage_id: str  # Unique request ID
    reasoning: Optional[str] = None  # LLM reasoning
    category: Optional[str] = None  # Query classification
    references: Optional[list[str]] = None  # Document references
    pdf_names: Optional[list[str]] = None  # PDF filenames
    image_results: Optional[dict[str, Any]] = None  # Image search results
    agent_results: Optional[list[AgentResult]] = None  # Per-agent results
    graph_data: Optional[Any] = None  # Chart/graph data
    knowledge_graph_visualization: Optional[Any] = None  # Knowledge graph
    shopping_results: Optional[Any] = None  # Shopping search results
    pdf_info: Optional[list[Any]] = None  # PDF metadata

    # Legacy fields for backward compatibility
    message_id: Optional[str] = None
    session_id: Optional[str] = None
    content: Optional[str] = None  # Alias for result
    agent_type: Optional[str] = None
    tokens_used: Optional[int] = None
    progress: int = 100


class ErrorEvent(BaseStreamEvent):
    """Error event."""
    event: str = "error"
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None


# Website-compatible API Response wrapper
class APIResponse(BaseModel):
    """Standard API response wrapper for website compatibility."""
    msg: str = "success"
    code: int = 0
    data: dict[str, Any]


class SearchResult(BaseModel):
    """Document search result."""
    file_id: str
    file_name: str
    content: str
    page: Optional[int] = None
    score: float
    metadata: Optional[dict[str, Any]] = None


class DocumentSearchResponse(BaseModel):
    """Document search response in website-compatible format."""
    msg: str = "success"
    code: int = 0
    data: dict[str, Any]
