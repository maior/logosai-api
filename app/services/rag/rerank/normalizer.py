"""Score normalization utilities."""

import logging
from typing import Optional

from app.services.rag.rerank.config import SCORE_NORMALIZERS

logger = logging.getLogger(__name__)


class ScoreNormalizer:
    """Normalize scores to 0-1 range."""

    def __init__(self):
        self.min_score = SCORE_NORMALIZERS["min_score"]
        self.max_score = SCORE_NORMALIZERS["max_score"]
        self.default_score = SCORE_NORMALIZERS["default_score"]

    def normalize_score(
        self,
        score: float,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> float:
        """
        Normalize a score to 0-1 range.

        Args:
            score: Original score to normalize
            min_val: Minimum value for normalization
            max_val: Maximum value for normalization

        Returns:
            Normalized score between 0 and 1
        """
        try:
            if min_val is None:
                min_val = self.min_score
            if max_val is None:
                max_val = self.max_score

            if min_val == max_val:
                return self.default_score

            normalized = (score - min_val) / (max_val - min_val)
            return max(0.0, min(1.0, normalized))

        except Exception as e:
            logger.error(f"Score normalization failed: {str(e)}")
            return self.default_score

    def normalize_scores(self, scores: list[float]) -> list[float]:
        """
        Normalize a list of scores.

        Args:
            scores: List of scores to normalize

        Returns:
            List of normalized scores
        """
        try:
            if not scores:
                return []

            min_val = min(scores)
            max_val = max(scores)

            return [self.normalize_score(score, min_val, max_val) for score in scores]

        except Exception as e:
            logger.error(f"Scores normalization failed: {str(e)}")
            return [self.default_score] * len(scores)

    def normalize_with_weights(
        self,
        scores: list[float],
        weights: list[float],
    ) -> float:
        """
        Normalize and combine multiple scores with weights.

        Args:
            scores: List of scores
            weights: List of weights

        Returns:
            Weighted normalized final score
        """
        try:
            if len(scores) != len(weights):
                logger.error("Scores and weights must have same length")
                return self.default_score

            normalized_scores = self.normalize_scores(scores)
            weighted_sum = sum(s * w for s, w in zip(normalized_scores, weights))
            weight_sum = sum(weights)

            if weight_sum == 0:
                return self.default_score

            final_score = weighted_sum / weight_sum
            return max(0.0, min(1.0, final_score))

        except Exception as e:
            logger.error(f"Weighted normalization failed: {str(e)}")
            return self.default_score

    def adjust_score_range(
        self,
        score: float,
        target_min: float = 0.3,
        target_max: float = 0.9,
    ) -> float:
        """
        Adjust score range to target range.

        Args:
            score: Score to adjust
            target_min: Target minimum value
            target_max: Target maximum value

        Returns:
            Adjusted score
        """
        try:
            return target_min + score * (target_max - target_min)
        except Exception as e:
            logger.error(f"Score range adjustment failed: {str(e)}")
            return self.default_score
