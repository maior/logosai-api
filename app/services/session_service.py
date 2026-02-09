"""Session service - DEPRECATED.

This module is deprecated. Use conversation_service.py instead.
In logosus schema:
- "Conversation" is for chat sessions
- "Session" is for authentication

This file exists only for backward compatibility.
"""

# Re-export from conversation_service for backward compatibility
from app.services.conversation_service import (
    ConversationService as SessionService,
    ConversationService,
)

__all__ = ["SessionService", "ConversationService"]
