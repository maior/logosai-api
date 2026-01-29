"""ACP Server client for agent communication."""

import json
import logging
from typing import Any, AsyncGenerator, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


class ACPClientError(Exception):
    """ACP Client error."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ACPClient:
    """Client for communicating with ACP (Agent Communication Protocol) server."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.acp_server_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def health_check(self) -> bool:
        """Check if ACP server is healthy."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"ACP health check failed: {e}")
            return False

    async def process_query(
        self,
        query: str,
        user_email: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process a query synchronously (non-streaming).

        Args:
            query: User query
            user_email: User's email
            session_id: Session ID
            project_id: Project ID
            context: Additional context

        Returns:
            Response from ACP server
        """
        session = await self._get_session()

        payload = {
            "query": query,
            "email": user_email,
            "session_id": session_id,
            "project_id": project_id,
            "context": context or {},
        }

        try:
            async with session.post(
                f"{self.base_url}/api/v1/process",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ACPClientError(
                        f"ACP server error: {error_text}",
                        status_code=response.status,
                    )
                return await response.json()
        except aiohttp.ClientError as e:
            raise ACPClientError(f"Failed to connect to ACP server: {e}")

    async def stream_query(
        self,
        query: str,
        user_email: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a query with streaming response.

        Args:
            query: User query
            user_email: User's email
            session_id: Session ID
            project_id: Project ID
            context: Additional context

        Yields:
            SSE events from ACP server
        """
        session = await self._get_session()

        payload = {
            "query": query,
            "email": user_email,
            "session_id": session_id,
            "project_id": project_id,
            "context": context or {},
        }

        try:
            async with session.post(
                f"{self.base_url}/api/v1/stream",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    yield {
                        "event": "error",
                        "data": {
                            "error_code": "ACP_ERROR",
                            "message": f"ACP server error: {error_text}",
                        },
                    }
                    return

                # Parse SSE stream
                buffer = ""
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode("utf-8")

                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        event = self._parse_sse_event(event_str)
                        if event:
                            yield event

        except aiohttp.ClientError as e:
            logger.error(f"ACP streaming error: {e}")
            yield {
                "event": "error",
                "data": {
                    "error_code": "CONNECTION_ERROR",
                    "message": f"Failed to connect to ACP server: {e}",
                },
            }

    def _parse_sse_event(self, event_str: str) -> Optional[dict[str, Any]]:
        """Parse SSE event string."""
        event_type = "message"
        data = ""

        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()

        if data:
            try:
                return {
                    "event": event_type,
                    "data": json.loads(data),
                }
            except json.JSONDecodeError:
                return {
                    "event": event_type,
                    "data": {"message": data},
                }

        return None


# Global client instance
_acp_client: Optional[ACPClient] = None


def get_acp_client() -> ACPClient:
    """Get global ACP client instance."""
    global _acp_client
    if _acp_client is None:
        _acp_client = ACPClient()
    return _acp_client


async def close_acp_client() -> None:
    """Close global ACP client."""
    global _acp_client
    if _acp_client:
        await _acp_client.close()
        _acp_client = None
