"""Reranking system configuration."""

# Scoring weights
DEFAULT_WEIGHTS = {
    "vector_weight": 0.6,
    "text_weight": 0.4,
    "quality_weight": 0.2,
    "length_weight": 0.1,
    "freshness_weight": 0.1,
    "context_weight": 0.3,
    "reference_weight": 0.1,
}

# Query type specific weights
QUERY_TYPE_WEIGHTS = {
    "technical": {
        "vector_weight": 0.7,
        "text_weight": 0.3,
    },
    "conceptual": {
        "vector_weight": 0.5,
        "text_weight": 0.5,
    },
    "default": DEFAULT_WEIGHTS.copy(),
}

# Score normalization parameters
SCORE_NORMALIZERS = {
    "min_score": 0.0,
    "max_score": 1.0,
    "default_score": 0.5,
}

# Document quality parameters
DOC_QUALITY_PARAMS = {
    "min_length": 100,
    "optimal_length": 1000,
    "max_length": 5000,
}

# Final score calculation weights
FINAL_SCORE_WEIGHTS = {
    "relevance": 0.4,
    "recency": 0.2,
    "technical": 0.2,
    "length": 0.1,
    "citation": 0.1,
}
