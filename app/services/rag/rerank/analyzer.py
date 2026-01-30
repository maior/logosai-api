"""Search behavior analyzer for reranking optimization."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SearchBehaviorAnalyzer:
    """Analyze user search behavior for reranking optimization."""

    def __init__(self):
        self.behavior_weights = {
            "satisfied": 1.0,  # No follow-up search
            "new_search": 0.8,  # New topic search
            "related_search": 0.4,  # Related search
            "refinement": 0.2,  # Query refinement
        }

    def analyze_chat_history(
        self,
        chat_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze chat history for search patterns.

        Args:
            chat_history: List of chat messages with queries and timestamps

        Returns:
            Analysis metrics dictionary
        """
        try:
            if not chat_history:
                return {}

            search_patterns = []
            for i in range(len(chat_history) - 1):
                current_query = chat_history[i].get("query", "")
                next_query = chat_history[i + 1].get("query", "")

                if current_query and next_query:
                    behavior = self.determine_search_behavior(
                        current_query,
                        next_query,
                        chat_history[i].get("timestamp"),
                        chat_history[i + 1].get("timestamp"),
                    )
                    search_patterns.append(
                        {
                            "current_query": current_query,
                            "next_query": next_query,
                            "behavior": behavior,
                        }
                    )

            return self.calculate_behavior_metrics(search_patterns)

        except Exception as e:
            logger.error(f"Chat history analysis failed: {e}")
            return {}

    def determine_search_behavior(
        self,
        current_query: str,
        next_query: str,
        current_time: Optional[float] = None,
        next_time: Optional[float] = None,
    ) -> str:
        """
        Determine search behavior type.

        Args:
            current_query: Current search query
            next_query: Next search query
            current_time: Current query timestamp
            next_time: Next query timestamp

        Returns:
            Behavior type string
        """
        try:
            # Check time interval
            if current_time and next_time:
                time_diff = next_time - current_time
                if time_diff > 300:  # More than 5 minutes
                    return "new_search"

            # Check query similarity
            similarity = self.calculate_query_similarity(current_query, next_query)

            if similarity > 0.8:
                return "refinement"
            elif similarity > 0.5:
                return "related_search"
            else:
                return "new_search"

        except Exception as e:
            logger.error(f"Search behavior determination failed: {e}")
            return "new_search"

    def calculate_query_similarity(self, query1: str, query2: str) -> float:
        """
        Calculate similarity between two queries.

        Args:
            query1: First query
            query2: Second query

        Returns:
            Similarity score (0-1)
        """
        try:
            # Simple word-based similarity (Jaccard)
            words1 = set(query1.lower().split())
            words2 = set(query2.lower().split())

            if not words1 or not words2:
                return 0.0

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            return len(intersection) / len(union)

        except Exception as e:
            logger.error(f"Query similarity calculation failed: {e}")
            return 0.0

    def calculate_behavior_metrics(
        self,
        search_patterns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate behavior metrics from search patterns.

        Args:
            search_patterns: List of search pattern dictionaries

        Returns:
            Metrics dictionary
        """
        try:
            if not search_patterns:
                return {}

            behavior_counts = {}
            for pattern in search_patterns:
                behavior = pattern.get("behavior", "unknown")
                behavior_counts[behavior] = behavior_counts.get(behavior, 0) + 1

            total = len(search_patterns)
            behavior_rates = {
                behavior: count / total
                for behavior, count in behavior_counts.items()
            }

            # Calculate satisfaction score
            satisfaction_score = sum(
                self.behavior_weights.get(behavior, 0.5) * rate
                for behavior, rate in behavior_rates.items()
            )

            return {
                "total_searches": total,
                "behavior_counts": behavior_counts,
                "behavior_rates": behavior_rates,
                "satisfaction_score": satisfaction_score,
            }

        except Exception as e:
            logger.error(f"Behavior metrics calculation failed: {e}")
            return {}

    def get_weight_adjustments(
        self,
        search_behavior: dict[str, Any],
    ) -> dict[str, float]:
        """
        Get weight adjustments based on search behavior.

        Args:
            search_behavior: Search behavior analysis results

        Returns:
            Weight adjustment dictionary
        """
        try:
            adjustments = {}

            satisfaction = search_behavior.get("satisfaction_score", 0.5)
            refinement_rate = search_behavior.get("behavior_rates", {}).get(
                "refinement", 0
            )

            # If high refinement rate, increase text weight
            if refinement_rate > 0.3:
                adjustments["text_weight"] = 1.2
                adjustments["vector_weight"] = 0.9

            # If low satisfaction, boost quality weight
            if satisfaction < 0.5:
                adjustments["quality_weight"] = 1.3
                adjustments["freshness_weight"] = 1.1

            return adjustments

        except Exception as e:
            logger.error(f"Weight adjustment calculation failed: {e}")
            return {}
