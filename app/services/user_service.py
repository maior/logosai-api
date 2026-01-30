"""User service for database operations.

Matches logos_server's logosai.users table schema.
Uses email as primary identifier (not UUID id).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserHistory
from app.schemas.user import UserCreate


class UserService:
    """Service for user-related database operations.

    Matches logos_server's user management pattern where email is the primary key.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email (primary lookup method).

        This is the main method for user lookup since logos_server uses
        email as the primary identifier.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    # Alias for compatibility
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID (email).

        For logos_server compatibility, user_id is actually the email.
        """
        return await self.get_by_email(user_id)

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user.

        Matches logos_server's INSERT INTO logosai.users pattern.
        """
        user = User(
            email=user_data.email,
            name=user_data.name,
            picture_url=user_data.picture_url,
            subscription_type="free",
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user: User) -> User:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def record_login_history(self, email: str, status: str = "success") -> None:
        """Record user login history.

        Matches logos_server's INSERT INTO logosai.user_history pattern.
        """
        history = UserHistory(
            user_email=email,
            access_type="login",
            status=status,
        )
        self.db.add(history)
        await self.db.flush()

    async def create_or_update_google_user(
        self,
        google_id: str,
        email: str,
        name: str,
        picture_url: Optional[str] = None,
    ) -> User:
        """Create or update user from Google OAuth.

        Matches logos_server's loaduser.py pattern:
        1. Check if user exists by email
        2. If exists, update last_login_at
        3. If not, create new user
        4. Record login history
        """
        # Try to find by email
        user = await self.get_by_email(email)

        if user:
            # Update existing user
            user.name = name
            user.picture_url = picture_url
            user.last_login_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(user)
        else:
            # Create new user
            user_data = UserCreate(
                email=email,
                name=name,
                picture_url=picture_url,
            )
            user = await self.create(user_data)

        # Record login history
        await self.record_login_history(email)

        return user
