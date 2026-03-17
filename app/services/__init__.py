"""Services package for business logic."""

from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.project_service import ProjectService
from app.services.session_service import SessionService
from app.services.chat_service import ChatService
from app.services.acp_client import ACPClient, get_acp_client, close_acp_client
from app.services.memory_service import MemoryService
from app.services.marketplace_service import MarketplaceService, MarketplaceServiceError

# RAG/Document services are optional (requires: pip install -e '.[rag]')
try:
    from app.services.document_service import DocumentService, DocumentServiceError
except ImportError:
    DocumentService = None
    DocumentServiceError = None

__all__ = [
    "AuthService",
    "UserService",
    "ProjectService",
    "SessionService",
    "ChatService",
    "ACPClient",
    "get_acp_client",
    "close_acp_client",
    "MemoryService",
    "DocumentService",
    "DocumentServiceError",
    "MarketplaceService",
    "MarketplaceServiceError",
]
