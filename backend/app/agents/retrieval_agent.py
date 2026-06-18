"""
Grid Retrieval Agent — wraps the hybrid retriever.

Reads:  envelope["masked_query"], envelope["filters"], envelope["tenant_id"]
Writes: envelope["retrieved"] = [chunk_dict, ...]
"""
from __future__ import annotations

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.rag.hybrid_retriever import HybridRetriever


class RetrievalAgent(BaseAgent):
    """Fetches the most relevant incident chunks from the hybrid (semantic + BM25) index."""

    name = "retrieval_agent"

    def __init__(self, settings, retriever: HybridRetriever):
        """Accept an injected HybridRetriever so the index is shared across requests."""
        super().__init__(settings)
        self.retriever = retriever

    def _run(self, env: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """Query the hybrid retriever and serialise the results into the envelope as plain dicts."""
        query = env.get("masked_query") or env.get("query", "")
        filters = env.get("filters") or None
        tenant_id = env.get("tenant_id") or "default"
        top_k = env.get("top_k") or self.settings.final_top_k

        chunks = self.retriever.retrieve(
            query, top_k=top_k, where=filters, tenant_id=tenant_id
        )
        env["retrieved"] = [
            {
                "id": c.id,
                "text": c.text,
                "metadata": c.metadata,
                "score": c.score,
                "semantic_rank": c.semantic_rank,
                "keyword_rank": c.keyword_rank,
            }
            for c in chunks
        ]
        return env, f"retrieved {len(chunks)} incidents from hybrid index"
