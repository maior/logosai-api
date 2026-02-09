"""
Response Normalizer - Pure functions for response format auto-correction.

Ensures logos_api responses match the format logos_web expects:
{
    "code": 0,
    "data": {
        "result": "답변 텍스트",
        "agent_results": [...],
        "metadata": {...},
        "knowledge_graph_visualization": null
    }
}

All functions are pure (no side effects) for easy testing.
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def normalize_final_result(data: dict) -> tuple[dict, list[str]]:
    """Normalize a final_result event's data to canonical format.

    Args:
        data: The raw data dict from a final_result event.

    Returns:
        Tuple of (normalized_data, list_of_corrections_applied).
    """
    corrections = []

    if not isinstance(data, dict):
        return {"code": 0, "data": {"result": str(data) if data else ""}}, [
            "non_dict_wrapped"
        ]

    # 1. Ensure top-level structure: {code, data: {result, agent_results, ...}}
    normalized = _ensure_top_level_structure(data, corrections)

    # 2. Unwrap double-nested data.data.result
    inner = normalized.get("data", {})
    inner = _unwrap_double_nesting(inner, corrections)
    normalized["data"] = inner

    # 3. Extract result from agent_results if missing
    inner = _ensure_result_field(inner, corrections)
    normalized["data"] = inner

    # 4. Clean result content (remove JSON codeblock markers, etc.)
    result = inner.get("result", "")
    if isinstance(result, str):
        cleaned = _clean_result_content(result)
        if cleaned != result:
            inner["result"] = cleaned
            corrections.append("content_cleaned")

    # 5. Ensure agent_results is a list
    if "agent_results" not in inner:
        inner["agent_results"] = []
    elif not isinstance(inner["agent_results"], list):
        inner["agent_results"] = []
        corrections.append("agent_results_reset_to_list")

    # 6. Ensure metadata exists
    if "metadata" not in inner:
        inner["metadata"] = {}

    if corrections:
        logger.info(f"📝 Response normalized: {', '.join(corrections)}")

    return normalized, corrections


def normalize_error_response(error: Any) -> dict:
    """Convert an error into a user-friendly response event.

    Maps technical errors to Korean-friendly messages.

    Args:
        error: The error (Exception, string, or dict).

    Returns:
        Canonical error event data.
    """
    error_str = str(error) if error else "Unknown error"
    error_lower = error_str.lower()

    # Classify error and generate user-friendly message
    if _is_connection_error(error_lower):
        user_message = "에이전트 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
        error_code = "CONNECTION_ERROR"
    elif _is_timeout_error(error_lower):
        user_message = "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
        error_code = "TIMEOUT_ERROR"
    elif _is_empty_response(error_lower):
        user_message = "에이전트가 응답을 생성하지 못했습니다. 다른 방식으로 질문해보세요."
        error_code = "EMPTY_RESPONSE"
    elif _is_auth_error(error_lower):
        user_message = "인증에 실패했습니다. 다시 로그인해주세요."
        error_code = "AUTH_ERROR"
    else:
        user_message = "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        error_code = "INTERNAL_ERROR"

    logger.warning(f"Error normalized: [{error_code}] {error_str[:200]}")

    return {
        "event": "final_result",
        "data": {
            "code": -1,
            "data": {
                "result": user_message,
                "agent_results": [],
                "metadata": {
                    "error": True,
                    "error_code": error_code,
                    "original_error": error_str[:500],
                },
                "knowledge_graph_visualization": None,
            },
        },
    }


def normalize_sync_response(data: dict) -> dict:
    """Normalize a synchronous chat response.

    Ensures the response matches {msg, code, data: {result, ...}} format.

    Args:
        data: Raw response dict.

    Returns:
        Normalized response dict.
    """
    if not isinstance(data, dict):
        return {
            "msg": "success",
            "code": 0,
            "data": {"result": str(data) if data else ""},
        }

    # Already has correct structure
    if "msg" in data and "code" in data and "data" in data:
        inner = data["data"]
        if isinstance(inner, dict) and "result" in inner:
            return data

    # Wrap if needed
    return {
        "msg": data.get("msg", "success"),
        "code": data.get("code", 0),
        "data": data.get("data", data),
    }


# --- Internal helpers ---


def _ensure_top_level_structure(data: dict, corrections: list) -> dict:
    """Ensure data has {code, data: {...}} structure."""
    # Already has the correct structure
    if "code" in data and "data" in data and isinstance(data["data"], dict):
        return data

    # Has nested data with code inside
    if "data" in data and isinstance(data["data"], dict):
        inner = data["data"]
        return {
            "code": inner.get("code", data.get("code", 0)),
            "data": inner,
        }

    # Flat structure - wrap it
    corrections.append("flat_structure_wrapped")
    return {
        "code": data.get("code", 0),
        "data": data,
    }


def _unwrap_double_nesting(inner: dict, corrections: list) -> dict:
    """Unwrap data.data.result → data.result if double-nested."""
    if not isinstance(inner, dict):
        return inner

    # Check for data.data.result pattern (3-level nesting)
    nested_data = inner.get("data")
    if isinstance(nested_data, dict) and "result" in nested_data:
        # This is the double-nesting: data: { data: { result: "..." } }
        # Flatten to data: { result: "..." }
        corrections.append("double_nested_unwrap")

        # Merge: keep outer fields, override with inner where both exist
        result = {}
        for key, value in inner.items():
            if key != "data":
                result[key] = value
        for key, value in nested_data.items():
            result[key] = value

        return result

    return inner


def _ensure_result_field(inner: dict, corrections: list) -> dict:
    """Ensure 'result' field exists with content."""
    if not isinstance(inner, dict):
        return inner

    result = inner.get("result")

    # Result already exists and has content
    if result and isinstance(result, str) and result.strip():
        return inner

    # Try to extract from agent_results
    agent_results = inner.get("agent_results", [])
    if isinstance(agent_results, list) and agent_results:
        assembled = _assemble_from_agent_results(agent_results)
        if assembled:
            inner["result"] = assembled
            corrections.append("answer_assembled_from_agents")
            return inner

    # Try 'answer' field
    if "answer" in inner and inner["answer"]:
        inner["result"] = inner["answer"]
        corrections.append("answer_field_mapped_to_result")
        return inner

    # Try 'content' field
    if "content" in inner and inner["content"]:
        inner["result"] = inner["content"]
        corrections.append("content_field_mapped_to_result")
        return inner

    # Try 'message' field (some agents return this)
    if "message" in inner and isinstance(inner["message"], str) and inner["message"]:
        inner["result"] = inner["message"]
        corrections.append("message_field_mapped_to_result")
        return inner

    return inner


def _assemble_from_agent_results(agent_results: list) -> str:
    """Extract and combine answers from agent_results list."""
    parts = []

    for ar in agent_results:
        if not isinstance(ar, dict):
            continue

        # Try various result field locations
        content = None
        result = ar.get("result")
        if isinstance(result, str) and result.strip():
            content = result
        elif isinstance(result, dict):
            content = (
                result.get("content")
                or result.get("answer")
                or result.get("result")
            )
            if isinstance(content, dict):
                content = content.get("answer") or content.get("content") or str(content)

        if not content:
            content = ar.get("content") or ar.get("answer")

        if content and isinstance(content, str) and content.strip():
            parts.append(content.strip())

    return "\n\n".join(parts)


def _clean_result_content(text: str) -> str:
    """Clean result text: remove JSON codeblock wrappers, etc."""
    text = text.strip()

    # Remove markdown JSON codeblock wrapper (entire text is JSON block)
    if text.startswith("```json") and text.endswith("```"):
        inner = text[7:-3].strip()
        try:
            parsed = json.loads(inner)
            # If it parses as JSON, extract meaningful content
            if isinstance(parsed, dict):
                return (
                    parsed.get("result")
                    or parsed.get("answer")
                    or parsed.get("content")
                    or inner
                )
        except json.JSONDecodeError:
            pass
        return inner

    # Handle JSON codeblock followed by actual content (e.g. ```json{...}```\n# Markdown...)
    if text.startswith("```json"):
        closing = text.find("```", 7)
        if closing > 0:
            after_block = text[closing + 3:].strip()
            if after_block:
                # Real content exists after JSON block — use it
                return after_block

    # Remove generic codeblock wrapper
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        if len(lines) > 2:
            return "\n".join(lines[1:-1]).strip()

    return text


def _is_connection_error(error: str) -> bool:
    return any(
        kw in error
        for kw in [
            "connectionerror",
            "connection refused",
            "cannot connect",
            "connect timeout",
            "name or service not known",
            "no route to host",
            "clientconnectorerror",
        ]
    )


def _is_timeout_error(error: str) -> bool:
    return any(
        kw in error
        for kw in ["timeout", "timed out", "deadline exceeded", "asynctimeouterror"]
    )


def _is_empty_response(error: str) -> bool:
    return any(
        kw in error
        for kw in ["no result", "empty response", "no response", "none response"]
    )


def _is_auth_error(error: str) -> bool:
    return any(
        kw in error
        for kw in [
            "unauthorized",
            "authentication",
            "401",
            "forbidden",
            "403",
            "invalid token",
        ]
    )
