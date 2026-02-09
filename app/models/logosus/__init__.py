"""Logosus schema models - Independent data layer for logos_api."""

from app.models.logosus.user import User, APIKey
from app.models.logosus.session import Session
from app.models.logosus.conversation import Conversation, Message
from app.models.logosus.project import Project
from app.models.logosus.document import Document, DocumentChunk
from app.models.logosus.rag import SearchHistory, RAGUsage
from app.models.logosus.analytics import UsageStats
from app.models.logosus.agent import ACPServer, RegisteredAgent
from app.models.logosus.memory import UserMemory

__all__ = [
    # User & Auth
    "User",
    "APIKey",
    "Session",
    # Chat
    "Conversation",
    "Message",
    # Project & Documents
    "Project",
    "Document",
    "DocumentChunk",
    # RAG
    "SearchHistory",
    "RAGUsage",
    # Analytics
    "UsageStats",
    # Agent Registry
    "ACPServer",
    "RegisteredAgent",
    # Memory
    "UserMemory",
]

# Schema name constant
SCHEMA_NAME = "logosus"
