"""
Response Middleware - SSE event wrapper for response normalization.

Wraps the raw SSE event generator to normalize final_result events
and handle errors gracefully. Non-final events pass through unchanged.
"""

import json
import logging
from typing import Any, AsyncGenerator

from app.middleware.response_normalizer import (
    normalize_final_result,
    normalize_error_response,
)

logger = logging.getLogger(__name__)


async def normalized_event_generator(
    raw_generator: AsyncGenerator[dict, None],
) -> AsyncGenerator[dict, None]:
    """Wrap a raw SSE event generator with response normalization.

    - final_result events: normalized to canonical format
    - error events: converted to user-friendly messages
    - all other events: pass through unchanged

    Args:
        raw_generator: Raw SSE event generator from orchestrator/chat service.

    Yields:
        Normalized SSE event dicts with {event, data} structure.
    """
    has_final_result = False

    try:
        async for event in raw_generator:
            event_type = event.get("event", "message")

            if event_type == "final_result":
                has_final_result = True
                # Normalize the final_result data
                event_data = event.get("data", {})
                if isinstance(event_data, str):
                    try:
                        event_data = json.loads(event_data)
                    except json.JSONDecodeError:
                        event_data = {"result": event_data}

                normalized, corrections = normalize_final_result(event_data)
                yield {
                    "event": "final_result",
                    "data": normalized,
                }

            elif event_type == "error":
                # Convert error to user-friendly final_result
                error_data = event.get("data", {})
                error_msg = ""
                if isinstance(error_data, dict):
                    error_msg = error_data.get("message", error_data.get("error", ""))
                elif isinstance(error_data, str):
                    error_msg = error_data

                error_event = normalize_error_response(error_msg)
                yield error_event

            else:
                # Pass through all other events unchanged
                yield event

    except Exception as e:
        logger.error(f"Stream error in normalized_event_generator: {e}")
        # If we haven't sent a final_result yet, send an error response
        if not has_final_result:
            yield normalize_error_response(e)
