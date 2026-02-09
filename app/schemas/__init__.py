"""Pydantic schemas package."""

from app.schemas.auth import (
    GoogleLoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenResponse,
    TokenPayload,
)
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserInDB,
)
from app.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectShareRequest,
    ProjectUpdate,
)
from app.schemas.session import (
    MessageBase,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    SessionBase,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    RegenerateRequest,
)
from app.schemas.document import (
    DocumentBase,
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentChunk,
    DocumentProcessingStatus,
)
from app.schemas.memory import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemoryListResponse,
    MemoryExtractRequest,
)
from app.schemas.marketplace import (
    AgentBase,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentDetailResponse,
    AgentSearchRequest,
    AgentStatsResponse,
    ReviewBase,
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewListResponse,
    PurchaseCreate,
    PurchaseResponse,
    PurchaseListResponse,
    CategoryResponse,
    CategoryListResponse,
)

__all__ = [
    # Auth schemas
    "GoogleLoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "TokenResponse",
    "TokenPayload",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "UserInDB",
    # Project schemas
    "ProjectBase",
    "ProjectCreate",
    "ProjectListResponse",
    "ProjectResponse",
    "ProjectShareRequest",
    "ProjectUpdate",
    # Session schemas
    "SessionBase",
    "SessionCreate",
    "SessionListResponse",
    "SessionResponse",
    "SessionUpdate",
    # Message schemas
    "MessageBase",
    "MessageCreate",
    "MessageListResponse",
    "MessageResponse",
    # Chat schemas
    "ChatRequest",
    "ChatResponse",
    "RegenerateRequest",
    # Document schemas
    "DocumentBase",
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentUploadResponse",
    "DocumentSearchRequest",
    "DocumentSearchResponse",
    "DocumentChunk",
    "DocumentProcessingStatus",
    # Memory schemas
    "MemoryCreate",
    "MemoryUpdate",
    "MemoryResponse",
    "MemoryListResponse",
    "MemoryExtractRequest",
    # Marketplace schemas
    "AgentBase",
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentListResponse",
    "AgentDetailResponse",
    "AgentSearchRequest",
    "AgentStatsResponse",
    "ReviewBase",
    "ReviewCreate",
    "ReviewUpdate",
    "ReviewResponse",
    "ReviewListResponse",
    "PurchaseCreate",
    "PurchaseResponse",
    "PurchaseListResponse",
    "CategoryResponse",
    "CategoryListResponse",
]
