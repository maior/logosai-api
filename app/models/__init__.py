"""SQLAlchemy models package.

Uses logosus schema for core logos_api models (independent from logos_server).
Marketplace models remain on logosai schema (shared with logos_server).
"""

# Core models from logosus schema (logos_api independent)
from app.models.logosus.user import User, APIKey
from app.models.logosus.conversation import Conversation, Message
from app.models.logosus.project import Project
from app.models.logosus.document import Document, DocumentChunk
from app.models.logosus.session import Session as AuthSession  # For authentication sessions
from app.models.logosus.rag import SearchHistory, RAGUsage
from app.models.logosus.analytics import UsageStats
from app.models.logosus.agent import ACPServer, RegisteredAgent
from app.models.logosus.memory import UserMemory

# Marketplace models from logosai schema (shared with logos_server)
from app.models.marketplace import (
    MarketplaceAgent,
    AgentReview,
    AgentPurchase,
    AgentStatus,
    PricingType,
)

# Legacy models for backward compatibility (deprecated - use logosus models)
from app.models.user import User as LegacyUser
from app.models.session import Session as LegacySession
from app.models.message import Message as LegacyMessage, MessageRole
from app.models.document import UserFile  # Legacy document model

__all__ = [
    # Core models (logosus)
    "User",
    "APIKey",
    "AuthSession",
    "Conversation",
    "Message",
    "Project",
    "Document",
    "DocumentChunk",
    "SearchHistory",
    "RAGUsage",
    "UsageStats",
    # Agent Registry (logosus)
    "ACPServer",
    "RegisteredAgent",
    # Memory
    "UserMemory",
    # Marketplace (logosai)
    "MarketplaceAgent",
    "AgentReview",
    "AgentPurchase",
    "AgentStatus",
    "PricingType",
    # Legacy (deprecated)
    "LegacyUser",
    "LegacySession",
    "LegacyMessage",
    "MessageRole",
    "UserFile",
]
