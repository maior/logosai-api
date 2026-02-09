"""Agent and ACP Server schemas for request/response validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- ACP Server Schemas ---


class ACPServerCreate(BaseModel):
    """Schema for creating an ACP server."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=500)
    is_active: bool = True
    is_default: bool = False
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ACPServerResponse(BaseModel):
    """Schema for ACP server response."""

    id: str
    name: str
    url: str
    is_active: bool
    is_default: bool
    health_status: str
    last_health_check: Optional[datetime] = None
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    agent_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Registered Agent Schemas ---


class AgentCreate(BaseModel):
    """Schema for manually registering an agent."""

    agent_id: str = Field(..., min_length=1, max_length=255)
    acp_server_id: Optional[str] = None  # If not provided, uses default ACP server
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    input_type: str = "query"
    output_type: str = "text"
    display_name: Optional[str] = None
    display_name_ko: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    priority: int = 50


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: str
    agent_id: str
    acp_server_id: str
    name: str
    description: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    input_type: str
    output_type: str
    display_name: Optional[str] = None
    display_name_ko: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    priority: int
    is_available: bool
    average_execution_time_ms: Optional[float] = None
    success_rate: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    source: str
    created_at: datetime
    updated_at: datetime

    # ACP server info (joined)
    acp_server_name: Optional[str] = None
    acp_server_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Response for agent listing."""

    agents: list[AgentResponse]
    total: int


# --- Sync Schemas ---


class SyncRequest(BaseModel):
    """Request to trigger ACP sync."""

    acp_server_id: Optional[str] = None  # If not provided, syncs default server


class SyncResponse(BaseModel):
    """Response from ACP sync."""

    added: int
    updated: int
    deactivated: int
    total: int
    acp_server_name: str
    acp_server_url: str
