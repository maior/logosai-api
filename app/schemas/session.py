"""Session schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionBase(BaseModel):
    """Base session schema."""
    title: Optional[str] = Field(None, max_length=500)


class SessionCreate(SessionBase):
    """Schema for creating a session."""
    project_id: Optional[str] = None


class SessionUpdate(BaseModel):
    """Schema for updating a session."""
    title: Optional[str] = Field(None, max_length=500)
    project_id: Optional[str] = None


class SessionResponse(SessionBase):
    """Schema for session response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    project_id: Optional[str] = None
    summary: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None


class SessionListResponse(BaseModel):
    """Schema for session list response."""
    sessions: list[SessionResponse]
    total: int


class MessageBase(BaseModel):
    """Base message schema."""
    role: str  # user, assistant, system
    content: str


class MessageCreate(MessageBase):
    """Schema for creating a message."""
    extra_data: Optional[dict] = None


class MessageResponse(MessageBase):
    """Schema for message response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    agent_type: Optional[str] = None
    tokens_used: Optional[int] = None
    extra_data: Optional[dict] = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """Schema for message list response."""
    messages: list[MessageResponse]
    total: int
