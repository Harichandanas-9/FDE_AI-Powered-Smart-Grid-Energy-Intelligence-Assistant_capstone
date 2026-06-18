"""
Admin / Model-Management endpoints (ADDITIVE — does not alter existing routes).

Backs the green-themed "Admin · System & Model Management" section:

  GET  /api/v1/config                  -> active configuration (read-only)
  POST /api/v1/config                  -> switch LLM provider/model at runtime
  POST /api/v1/admin/reset-index       -> drop + recreate the vector collection
  POST /api/v1/admin/validate-retrieval-> run a test query through the retriever

Design notes
------------
- Everything here REUSES existing services (vector_store.reset_collection,
  HybridRetriever, get_settings). No response schema of an existing route is
  changed, so the frontend stays backward compatible.
- Provider switching mutates the cached Settings singleton and clears the
  cached orchestrator in routes_analyze so the next /analyze picks it up.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_principal

logger = get_logger(__name__)
router = APIRouter(tags=["admin"])

# Options surfaced in the frontend dropdowns. Only providers with a working
# code path are marked functional; the rest are shown for completeness.
EMBEDDING_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-small-en-v1.5",
    "hash",  # offline, dependency-free (default for the demo)
]
VECTOR_STORES = ["chroma", "faiss"]
LLM_PROVIDERS = ["groq", "gemini", "openai", "anthropic", "ollama", "template"]


def _vector_count() -> Optional[int]:
    """Return the number of vectors currently stored in the ChromaDB collection, or None on error."""
    try:
        from app.rag.vector_store import get_client, get_or_create_collection, count
        s = get_settings()
        return count(get_or_create_collection(get_client(s.chroma_persist_dir)))
    except Exception:
        return None


@router.get("/config", summary="Active system configuration (read-only)")
async def get_config(principal: dict = Depends(get_current_principal)) -> Dict[str, Any]:
    """Return the active system configuration including provider, model, embedding, and vector-store info."""
    s = get_settings()
    has_key = bool(
        (s.llm_provider == "groq" and s.groq_api_key)
        or (s.llm_provider == "gemini" and s.gemini_api_key)
        or (s.llm_provider == "openai" and s.openai_api_key)
        or (s.llm_provider == "anthropic" and s.anthropic_api_key)
    )
    return {
        "dataset": "smart_grid_stability_augmented.csv",
        "embedding_model": s.embedding_model,
        "vector_store": "chroma",
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "llm_mode": "live" if has_key else "offline_template_fallback",
        "vectors_indexed": _vector_count(),
        "options": {
            "embedding_models": EMBEDDING_MODELS,
            "vector_stores": VECTOR_STORES,
            "llm_providers": LLM_PROVIDERS,
        },
    }


class ConfigUpdate(BaseModel):
    """Request body for runtime LLM provider/model switching."""

    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


@router.post("/config", summary="Switch LLM provider/model at runtime (safe)")
async def set_config(
    body: ConfigUpdate, request: Request,
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Switch the LLM provider and/or model at runtime without restarting the server.

    The cached orchestrator and RAG pipeline are invalidated so the next request
    picks up the new provider settings.
    """
    s = get_settings()
    changed = {}
    if body.llm_provider and body.llm_provider in LLM_PROVIDERS:
        s.llm_provider = body.llm_provider
        changed["llm_provider"] = body.llm_provider
    if body.llm_model:
        s.llm_model = body.llm_model
        changed["llm_model"] = body.llm_model

    # Clear cached orchestrator + rag pipeline so the next request rebuilds
    # with the new provider. Safe: they lazily recreate on demand.
    try:
        from app.api import routes_analyze
        routes_analyze._ORCH = None
    except Exception:
        pass

    logger.info("config_updated", extra={"changed": changed})
    return {"status": "ok", "changed": changed,
            "active": {"llm_provider": s.llm_provider, "llm_model": s.llm_model}}


@router.post("/admin/reset-index", summary="Drop + recreate the vector collection")
async def reset_index(
    request: Request, principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Drop and recreate the ChromaDB vector collection, also invalidating the BM25 index and analytics cache."""
    s = get_settings()
    try:
        from app.rag.vector_store import get_client, reset_collection
        reset_collection(get_client(s.chroma_persist_dir))
        # Invalidate BM25 + analytics cache so widgets reflect the reset
        if hasattr(request.app.state, "bm25_index"):
            request.app.state.bm25_index = None
        try:
            from app.services.analytics_service import bust_fetch_cache
            bust_fetch_cache()
        except Exception:
            pass
        return {"status": "ok", "message": "Vector index reset. Re-ingest to repopulate.",
                "vectors_indexed": _vector_count()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("reset_index_failed", extra={"err": str(exc)})
        return {"status": "error", "message": f"{exc.__class__.__name__}: {exc}"}


class ValidateBody(BaseModel):
    """Request body for the validate-retrieval smoke test."""

    query: str = "transformer overload during peak demand causing voltage instability"
    top_k: int = 5


@router.post("/admin/validate-retrieval", summary="Run a test query through the retriever")
async def validate_retrieval(
    body: ValidateBody, request: Request,
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Run a test query through the hybrid retriever and return the top-k hits with latency.

    Useful for confirming that the vector index is populated and retrieval is functioning.
    """
    s = get_settings()
    t0 = time.time()
    try:
        from app.rag.hybrid_retriever import HybridRetriever
        bm25 = getattr(request.app.state, "bm25_index", None)
        retr = HybridRetriever(s, bm25_index=bm25)
        hits = retr.retrieve(body.query, top_k=body.top_k)
        results: List[Dict[str, Any]] = [
            {
                "id": h.id,
                "score": h.score,
                "semantic_rank": h.semantic_rank,
                "keyword_rank": h.keyword_rank,
                "region": (h.metadata or {}).get("region"),
                "severity": (h.metadata or {}).get("severity"),
                "preview": (h.text or "")[:160],
            }
            for h in hits
        ]
        return {
            "status": "ok" if results else "empty",
            "query": body.query,
            "n_results": len(results),
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "results": results,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("validate_retrieval_failed", extra={"err": str(exc)})
        return {"status": "error", "message": f"{exc.__class__.__name__}: {exc}",
                "latency_ms": round((time.time() - t0) * 1000, 1)}
