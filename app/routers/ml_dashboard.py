"""ML Dashboard endpoints for GNN+RL agent selection visualization.

Read-only endpoints exposing HybridAgentSelector metrics,
selection history, and training loss for the monitoring dashboard.
"""

import logging
import os
import sys
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter()

# Add ontology to path (same pattern as orchestrator_service.py)
_logos_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
for p in [_logos_root, os.path.join(_logos_root, 'ontology')]:
    _abs = os.path.abspath(p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)


def _get_hybrid_selector():
    """Lazy import HybridAgentSelector singleton."""
    try:
        from ontology.core.hybrid_agent_selector import get_hybrid_selector
        return get_hybrid_selector()
    except Exception as e:
        logger.warning(f"HybridAgentSelector not available: {e}")
        return None


def _get_kg_engine():
    """Lazy import KnowledgeGraphEngine singleton."""
    try:
        from ontology.engines.knowledge_graph_clean import get_knowledge_graph_engine
        return get_knowledge_graph_engine()
    except Exception as e:
        logger.warning(f"KnowledgeGraphEngine not available: {e}")
        return None


@router.get("/stats")
async def get_ml_stats() -> dict[str, Any]:
    """Full stats including selection_history and training_history."""
    selector = _get_hybrid_selector()
    if not selector:
        return {"available": False, "message": "GNN+RL system not initialized"}

    stats = selector.get_stats()
    return {"available": True, **stats}


@router.get("/selection-methods")
async def get_selection_method_breakdown() -> dict[str, Any]:
    """Method breakdown for donut chart."""
    selector = _get_hybrid_selector()
    if not selector:
        return {"available": False}

    stats = selector.get_stats()
    return {
        "available": True,
        "total": stats.get("total_selections", 0),
        "methods": {
            "gnn_rl": stats.get("gnn_rl_selections", 0),
            "gnn_rl_fallback": stats.get("gnn_rl_fallback", 0),
            "graph_assisted": stats.get("graph_assisted", 0),
            "llm_only": stats.get("llm_only", 0),
        },
        "feedback_stored": stats.get("feedback_stored", 0),
    }


@router.get("/knowledge-graph")
async def get_knowledge_graph(
    max_nodes: int = Query(80, ge=1, le=500),
) -> dict[str, Any]:
    """Knowledge Graph visualization data for the dashboard."""
    kg = _get_kg_engine()
    if not kg:
        return {"available": False, "nodes": [], "edges": [], "stats": {}}

    try:
        viz = kg._generate_visualization_sync(max_nodes=max_nodes)
        stats = kg.get_graph_stats()

        # Add 'size' field to edges (frontend KnowledgeGraphEdge requires it)
        for edge in viz.get("edges", []):
            edge.setdefault("size", 1)

        return {
            "available": True,
            "nodes": viz.get("nodes", []),
            "edges": viz.get("edges", []),
            "metadata": viz.get("metadata", {}),
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Knowledge graph visualization failed: {e}")
        return {"available": False, "nodes": [], "edges": [], "stats": {}, "error": str(e)}
