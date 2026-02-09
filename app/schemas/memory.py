"""Pydantic schemas for user memory system."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    """Schema for creating a user memory."""

    content: str = Field(..., min_length=1, max_length=2000)
    memory_type: str = Field(..., pattern=r"^(fact|preference|context|instruction)$")
    category: Optional[str] = Field(None, max_length=100)
    importance: float = Field(0.5, ge=0.0, le=1.0)


class MemoryUpdate(BaseModel):
    """Schema for updating a user memory."""

    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    memory_type: Optional[str] = Field(None, pattern=r"^(fact|preference|context|instruction)$")
    category: Optional[str] = Field(None, max_length=100)
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    """Schema for memory response."""

    id: str
    user_id: str
    memory_type: str
    content: str
    category: Optional[str] = None
    importance: float
    source_conversation_id: Optional[str] = None
    is_active: bool
    access_count: int
    last_accessed_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    """Response for memory listing."""

    memories: list[MemoryResponse]
    total: int


class MemoryExtractRequest(BaseModel):
    """Request to manually extract memories from a conversation."""

    conversation_id: str
