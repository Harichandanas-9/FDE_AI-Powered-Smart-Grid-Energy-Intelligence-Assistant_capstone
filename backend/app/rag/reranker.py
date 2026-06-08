"""
Hybrid reranking — two modes, auto-selected at runtime.

Mode 1: CrossEncoder (ms-marco-MiniLM-L-6-v2)
  - Reads (query, candidate) pairs; highest fidelity.
  - Requires sentence-transformers + torch (~100 MB model, ~200 ms/query).
  - Used when sentence-transformers loads successfully.

Mode 2: ScoreFusionReranker  ← NEW fallback
  - Normalizes raw semantic similarity scores (from ChromaDB) and BM25 scores
    independently to [0, 1] then computes a weighted sum.
  - No additional model download; runs in microseconds.
  - Used automatically when CrossEncoder cannot be loaded.

Public API
----------
    from app.rag.reranker import rerank

    results = rerank(
        query,
        chunks,                      # List[RetrievedChunk]
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k=5,
        sem_scores={chunk_id: float, ...},   # raw semantic similarity per chunk
        bm25_scores={chunk_id: float, ...},  # raw BM25 score per chunk
        sem_weight=0.6,
        bm25_weight=0.4,
    )

If *model_name* is None or CrossEncoder fails, ScoreFusionReranker is used
automatically (requires sem_scores / bm25_scores passed in).
"""
from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.rag.hybrid_retriever import RetrievedChunk

logger = get_logger(__name__)

_CE_MODEL = None
_CE_LOCK = Lock()


# ---------------------------------------------------------------------------
# CrossEncoder (Tier 1)
# ---------------------------------------------------------------------------

def _load_cross_encoder(model_name: str):
    from sentence_transformers import CrossEncoder  # noqa: PLC0415
    logger.info("loading_cross_encoder", extra={"model": model_name})
    return CrossEncoder(model_name, device="cpu")


def _get_cross_encoder(model_name: str):
    global _CE_MODEL
    if _CE_MODEL is not None:
        return _CE_MODEL
    with _CE_LOCK:
        if _CE_MODEL is None:
            _CE_MODEL = _load_cross_encoder(model_name)
    return _CE_MODEL


def _cross_encoder_rerank(
    query: str,
    chunks: List[RetrievedChunk],
    model_name: str,
    top_k: Optional[int],
) -> List[RetrievedChunk]:
    model = _get_cross_encoder(model_name)
    pairs = [(query, c.text) for c in chunks]
    scores = model.predict(pairs)
    rescored = [
        RetrievedChunk(
            id=c.id, text=c.text, metadata=c.metadata,
            score=float(s),
            semantic_rank=c.semantic_rank,
            keyword_rank=c.keyword_rank,
        )
        for c, s in zip(chunks, scores)
    ]
    rescored.sort(key=lambda x: -x.score)
    return rescored[:top_k] if top_k else rescored


# ---------------------------------------------------------------------------
# ScoreFusionReranker (Tier 2 — no model required)
# ---------------------------------------------------------------------------

def _normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a score dict to [0, 1]."""
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi != lo else 1.0
    return {k: (v - lo) / span for k, v in scores.items()}


def _score_fusion_rerank(
    chunks: List[RetrievedChunk],
    sem_scores: Dict[str, float],
    bm25_scores: Dict[str, float],
    sem_weight: float,
    bm25_weight: float,
    top_k: Optional[int],
) -> List[RetrievedChunk]:
    """
    Normalize BM25 and semantic scores independently, then combine:
        final = sem_weight * norm_sem + bm25_weight * norm_bm25
    Falls back gracefully when either score set is empty.
    """
    norm_sem = _normalize(sem_scores)
    norm_bm25 = _normalize(bm25_scores)

    rescored: List[RetrievedChunk] = []
    for c in chunks:
        s = (sem_weight * norm_sem.get(c.id, 0.0)
             + bm25_weight * norm_bm25.get(c.id, 0.0))
        rescored.append(
            RetrievedChunk(
                id=c.id, text=c.text, metadata=c.metadata,
                score=round(s, 6),
                semantic_rank=c.semantic_rank,
                keyword_rank=c.keyword_rank,
            )
        )

    rescored.sort(key=lambda x: -x.score)
    return rescored[:top_k] if top_k else rescored


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def rerank(
    query: str,
    chunks: List[RetrievedChunk],
    *,
    model_name: Optional[str] = None,
    top_k: Optional[int] = None,
    sem_scores: Optional[Dict[str, float]] = None,
    bm25_scores: Optional[Dict[str, float]] = None,
    sem_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> List[RetrievedChunk]:
    """
    Rerank *chunks* for *query*.

    Tries CrossEncoder first (if model_name provided); falls back to
    ScoreFusionReranker using sem_scores + bm25_scores.
    If neither works, returns the input list truncated to top_k.
    """
    if not chunks:
        return []

    # --- Try CrossEncoder ---
    if model_name:
        try:
            result = _cross_encoder_rerank(query, chunks, model_name, top_k)
            logger.info("cross_encoder_reranked", extra={"n": len(result)})
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("cross_encoder_failed_falling_back_to_score_fusion",
                           extra={"err": str(exc)})

    # --- Score fusion fallback ---
    if sem_scores or bm25_scores:
        result = _score_fusion_rerank(
            chunks,
            sem_scores or {},
            bm25_scores or {},
            sem_weight,
            bm25_weight,
            top_k,
        )
        logger.info("score_fusion_reranked", extra={"n": len(result)})
        return result

    # --- Identity fallback ---
    logger.info("rerank_identity_fallback", extra={"n": len(chunks)})
    return chunks[:top_k] if top_k else chunks
