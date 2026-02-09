"""ACP Server and Registered Agent models for logosus schema.

Provides DB-backed dynamic agent registry, replacing hardcoded DEFAULT_AGENTS
in ontology/orchestrator/agent_registry.py.

Supports multiple ACP servers for future multi-server architecture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin


class ACPServer(LogosusBase, TimestampMixin):
    """ACP Server connection information.

    Stores connection details for ACP (Agent Communication Protocol) servers.
    Each server hosts multiple agents. Supports multi-server architecture
    where agents can be distributed across different servers.
    """

    __tablename__ = "acp_servers"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(
        String(20), default="unknown"
    )  # healthy, unhealthy, unknown
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Extra info
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    # Relationships
    agents: Mapped[list["RegisteredAgent"]] = relationship(
        "RegisteredAgent",
        back_populates="acp_server",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ACPServer {self.name} ({self.url})>"


class RegisteredAgent(LogosusBase, TimestampMixin):
    """Registered agent metadata.

    Stores agent information from ACP servers. This replaces the hardcoded
    DEFAULT_AGENTS in ontology/orchestrator/agent_registry.py.

    The agent_id is the unique identifier used by ACP server to identify
    and execute the agent (e.g., 'internet_agent', 'weather_agent').
    """

    __tablename__ = "registered_agents"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Agent identification
    agent_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    acp_server_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.acp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Agent metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    # I/O schema
    input_type: Mapped[str] = mapped_column(String(50), default="query")
    output_type: Mapped[str] = mapped_column(String(50), default="text")

    # Display information
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name_ko: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)

    # Status and metrics
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    average_execution_time_ms: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(50), default="acp_sync"
    )  # acp_sync, manual, seed

    # Relationships
    acp_server: Mapped["ACPServer"] = relationship(
        "ACPServer", back_populates="agents"
    )

    def __repr__(self) -> str:
        return f"<RegisteredAgent {self.agent_id}>"

    def to_registry_dict(self) -> dict:
        """Convert to dict format compatible with ontology AgentRegistryEntry."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description or "",
            "capabilities": self.capabilities or [],
            "tags": self.tags or [],
            "input_type": self.input_type,
            "output_type": self.output_type,
            "display_name": self.display_name,
            "display_name_ko": self.display_name_ko,
            "icon": self.icon,
            "color": self.color,
            "priority": self.priority,
        }
