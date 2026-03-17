"""API Routers package."""

from app.routers import auth, users, projects, sessions, chat, health, marketplace

__all__ = ["auth", "users", "projects", "sessions", "chat", "health", "marketplace"]

# RAG/Document router is optional
try:
    from app.routers import documents, rag
    __all__ += ["documents", "rag"]
except ImportError:
    pass
