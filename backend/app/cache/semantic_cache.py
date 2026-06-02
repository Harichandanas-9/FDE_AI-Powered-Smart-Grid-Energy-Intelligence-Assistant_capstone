"""Semantic cache — skips LLM calls for near-duplicate queries (cosine ≥ threshold)."""
from __future__ import annotations

import math
import threading
from typing import Any, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x * x for x in a))
    mb  = math.sqrt(sum(x * x for x in b))
    return dot / (ma * mb) if ma and mb else 0.0


class SemanticCache:
    def __init__(self, threshold: float = 0.92, max_items: int = 500) -> None:
        self._lock      = threading.Lock()
        self._entries: List[Tuple[List[float], str, Any]] = []
        self._threshold = threshold
        self._max       = max_items

    def get(self, query_emb: List[float]) -> Optional[Any]:
        with self._lock:
            best, best_r = 0.0, None
            for emb, _, result in self._entries:
                s = _cosine(query_emb, emb)
                if s > best:
                    best, best_r = s, result
            if best >= self._threshold:
                logger.debug(f"[semantic_cache] HIT score={best:.3f}")
                return best_r
        return None

    def put(self, query_emb: List[float], query: str, result: Any) -> None:
        with self._lock:
            if len(self._entries) >= self._max:
                self._entries = self._entries[-(self._max // 2):]
            self._entries.append((query_emb, query, result))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)


def _build() -> SemanticCache:
    try:
        from app.core.config import get_settings
        s = get_settings()
        return SemanticCache(
            threshold=getattr(s, "semantic_cache_threshold", 0.92),
            max_items=getattr(s, "semantic_cache_max_items",  500),
        )
    except Exception:
        return SemanticCache()


semantic_cache = _build()
