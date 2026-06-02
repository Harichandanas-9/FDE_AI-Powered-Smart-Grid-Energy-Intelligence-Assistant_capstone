"""
Optional cross-encoder reranking.

Cross-encoders read (query, candidate) as a pair and score relevance with much
higher fidelity than bi-encoders (sentence-transformers). The trade-off is
~100 MB model + ~200 ms per query.

Strategy
--------
- Off by default (configurable).
- When off, returns the input list unchanged.
- When on, scores each candidate with `ms-marco-MiniLM-L-6-v2` and re-sorts.
"""
from __future__ import annotations

from threading import Lock
from typing import List, Optional

from app.core.logging import get_logger
from app.rag.hybrid_retriever import RetrievedChunk

logger = get_logger(__name__)

_MODEL = None
_LOCK = Lock()


def _load(model_name: str):
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed; cannot use reranker."
        ) from exc
    logger.info("loading_reranker", extra={"model": model_name})
    return CrossEncoder(model_name, device="cpu")


def get_reranker(model_name: str):
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is None:
            _MODEL = _load(model_name)
    return _MODEL


def rerank(
    query: str,
    chunks: List[RetrievedChunk],
    *,
    model_name: Optional[str] = None,
    top_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    if not chunks or not model_name:
        return chunks[:top_k] if top_k else chunks
    try:
        model = get_reranker(model_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reranker_disabled", extra={"err": str(exc)})
        return chunks[:top_k] if top_k else chunks

    pairs = [(query, c.text) for c in chunks]
    scores = model.predict(pairs)
    # Combine scores: keep RetrievedChunk identity, overwrite score field
    rescored = [
        RetrievedChunk(
            id=c.id, text=c.text, metadata=c.metadata,
            score=float(s), semantic_rank=c.semantic_rank, keyword_rank=c.keyword_rank
        )
        for c, s in zip(chunks, scores)
    ]
    rescored.sort(key=lambda x: -x.score)
    return rescored[:top_k] if top_k else rescored
