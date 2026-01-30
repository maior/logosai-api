"""Utility functions for reranking system."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Query type keywords
TECHNICAL_KEYWORDS = {
    "how",
    "implement",
    "error",
    "bug",
    "code",
    "function",
    "class",
    "method",
    "api",
    "debug",
    "fix",
    "configure",
    "setup",
    "install",
    "구현",
    "에러",
    "버그",
    "코드",
    "함수",
    "설정",
    "설치",
}

CONCEPTUAL_KEYWORDS = {
    "what",
    "why",
    "explain",
    "difference",
    "compare",
    "concept",
    "theory",
    "definition",
    "meaning",
    "무엇",
    "왜",
    "설명",
    "차이",
    "비교",
    "개념",
    "이론",
    "정의",
}


def detect_query_type(query: str) -> str:
    """
    Detect query type based on content.

    Args:
        query: Search query string

    Returns:
        Query type: 'technical', 'conceptual', or 'default'
    """
    try:
        query_words = set(query.lower().split())

        if any(keyword in query_words for keyword in TECHNICAL_KEYWORDS):
            return "technical"
        elif any(keyword in query_words for keyword in CONCEPTUAL_KEYWORDS):
            return "conceptual"

        return "default"

    except Exception as e:
        logger.error(f"Query type detection error: {e}")
        return "default"


def log_reranking_stats(results: list[dict[str, Any]]) -> None:
    """
    Log reranking statistics.

    Args:
        results: List of reranked documents with scores
    """
    try:
        scores = [doc.get("final_score", 0) for doc in results]
        if scores:
            logger.info(
                f"Reranking stats: min={min(scores):.3f}, "
                f"max={max(scores):.3f}, "
                f"avg={sum(scores)/len(scores):.3f}, "
                f"count={len(scores)}"
            )
    except Exception as e:
        logger.error(f"Logging stats error: {e}")


def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    """
    Extract keywords from text.

    Args:
        text: Input text
        max_keywords: Maximum number of keywords

    Returns:
        List of keywords
    """
    try:
        import re

        # Remove special characters
        text = re.sub(r"[^\w\s]", " ", text.lower())
        words = text.split()

        # Filter stopwords (basic)
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "and",
            "or",
            "but",
            "not",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
        }

        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        # Count frequency
        freq = {}
        for word in keywords:
            freq[word] = freq.get(word, 0) + 1

        # Sort by frequency
        sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        return [word for word, _ in sorted_keywords[:max_keywords]]

    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        return []
