"""Reranking metrics and performance tracking."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RerankingMetrics:
    """Track and analyze reranking performance."""

    def __init__(self):
        self.metrics_history: list[dict[str, Any]] = []
        self.max_history = 1000

    def record_reranking_result(
        self,
        query: str,
        group: str,
        search_behavior: str,
        timestamp: float,
    ) -> None:
        """
        Record a reranking result.

        Args:
            query: Search query
            group: Test group (A/B)
            search_behavior: User search behavior type
            timestamp: Timestamp of the search
        """
        try:
            metric = {
                "query": query,
                "group": group,
                "behavior": search_behavior,
                "timestamp": timestamp,
            }
            self.metrics_history.append(metric)

            # Limit history size
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history :]

            # Periodic performance analysis
            if len(self.metrics_history) % 100 == 0:
                self.analyze_performance()

        except Exception as e:
            logger.error(f"Failed to record reranking result: {e}")

    def analyze_performance(self) -> dict[str, float]:
        """
        Analyze reranking performance.

        Returns:
            Performance scores by group
        """
        try:
            group_metrics = {
                "A": {"total": 0, "satisfied": 0, "refinement": 0},
                "B": {"total": 0, "satisfied": 0, "refinement": 0},
            }

            for metric in self.metrics_history:
                group = metric.get("group", "A")
                behavior = metric.get("behavior", "")

                if group not in group_metrics:
                    continue

                group_metrics[group]["total"] += 1
                if behavior == "satisfied":
                    group_metrics[group]["satisfied"] += 1
                elif behavior == "refinement":
                    group_metrics[group]["refinement"] += 1

            # Calculate performance scores
            scores = {}
            for group in ["A", "B"]:
                total = group_metrics[group]["total"]
                if total > 0:
                    satisfaction_rate = group_metrics[group]["satisfied"] / total
                    refinement_rate = group_metrics[group]["refinement"] / total
                    scores[group] = satisfaction_rate - refinement_rate

            logger.info(f"Performance analysis: {scores}")
            return scores

        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            return {}

    async def calculate_scores(
        self,
        query: str,
        document: dict[str, Any],
        query_type: str = "default",
    ) -> dict[str, float]:
        """
        Calculate various scores for a document.

        Args:
            query: Search query
            document: Document to score
            query_type: Type of query

        Returns:
            Dictionary of scores
        """
        try:
            content = document.get("content", "")
            metadata = document.get("metadata", {})

            # Relevance score (basic keyword matching)
            query_words = set(query.lower().split())
            content_lower = content.lower()
            matching_words = sum(1 for word in query_words if word in content_lower)
            relevance = min(1.0, matching_words / max(len(query_words), 1))

            # Length score
            content_length = len(content)
            if content_length < 100:
                length_score = content_length / 100
            elif content_length <= 1000:
                length_score = 1.0
            else:
                length_score = max(0.5, 1.0 - (content_length - 1000) / 4000)

            # Technical score (for technical queries)
            technical_score = 0.5
            if query_type == "technical":
                code_indicators = ["```", "def ", "class ", "function", "import "]
                technical_score = (
                    min(1.0, sum(1 for ind in code_indicators if ind in content) / 3)
                    if any(ind in content for ind in code_indicators)
                    else 0.3
                )

            # Recency score
            recency_score = 0.5
            if "created_at" in metadata or "reg_date" in metadata:
                from datetime import datetime, timezone

                date_str = metadata.get("created_at") or metadata.get("reg_date")
                try:
                    if isinstance(date_str, str):
                        created = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                        age_days = (datetime.now(timezone.utc) - created).days
                        recency_score = max(0.1, 1.0 - age_days / 365)
                except Exception:
                    pass

            # Citation score (presence of references)
            citation_indicators = ["reference", "citation", "doi:", "http", "참고"]
            citation_score = (
                min(1.0, sum(1 for ind in citation_indicators if ind.lower() in content_lower) / 2)
            )

            return {
                "relevance": relevance,
                "recency": recency_score,
                "technical": technical_score,
                "length": length_score,
                "citation": citation_score,
            }

        except Exception as e:
            logger.error(f"Score calculation error: {e}")
            return {
                "relevance": 0.0,
                "recency": 0.5,
                "technical": 0.5,
                "length": 0.5,
                "citation": 0.0,
            }

    def get_statistics(self) -> dict[str, Any]:
        """Get overall statistics."""
        try:
            if not self.metrics_history:
                return {"total_queries": 0}

            behaviors = {}
            for metric in self.metrics_history:
                behavior = metric.get("behavior", "unknown")
                behaviors[behavior] = behaviors.get(behavior, 0) + 1

            return {
                "total_queries": len(self.metrics_history),
                "behavior_distribution": behaviors,
                "performance_scores": self.analyze_performance(),
            }

        except Exception as e:
            logger.error(f"Statistics calculation error: {e}")
            return {"error": str(e)}
