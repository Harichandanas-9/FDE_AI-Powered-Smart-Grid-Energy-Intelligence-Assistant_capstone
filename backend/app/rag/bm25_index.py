"""
BM25 keyword index over the chunks produced by STEP 3.

Why BM25
--------
Semantic embeddings are great at concepts but weak at exact identifiers
("T-104", "F-12", "Substation Alpha"). BM25 catches those. We persist the
index as a pickle so server restarts don't re-tokenize the corpus.

Public API
----------
    index = build_bm25_index(chunks: list[dict]) -> BM25Index
    BM25Index.save(path)  /  BM25Index.load(path)
    BM25Index.search(query, top_k) -> list[(chunk_id, score)]
"""
from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase + alphanumeric tokens. Cheap, no NLTK dependency at runtime."""
    return _TOKEN.findall((text or "").lower())


@dataclass
class BM25Index:
    """In-memory BM25 index backed by rank_bm25.BM25Okapi.

    Stores tokenized documents alongside their chunk IDs so search results
    can be correlated with the original chunk dicts.
    """

    chunk_ids: List[str]
    documents: List[List[str]]  # tokenized
    bm25: object                # rank_bm25.BM25Okapi instance

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """Return up to top_k (chunk_id, score) pairs ranked by BM25 relevance."""
        if not self.chunk_ids:
            return []
        toks = tokenize(query)
        if not toks:
            return []
        scores = self.bm25.get_scores(toks)
        # Sort by score desc, take top_k, filter zero-scores
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:top_k]
        return [(self.chunk_ids[i], float(s)) for i, s in ranked if s > 0]

    def save(self, path: Path) -> None:
        """Pickle the index to disk, creating parent directories as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {"chunk_ids": self.chunk_ids,
                 "documents": self.documents,
                 "bm25": self.bm25},
                f,
            )
        logger.info("bm25_saved", extra={"path": str(path), "n_docs": len(self.chunk_ids)})

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        """Deserialize a previously saved BM25Index from a pickle file."""
        with open(path, "rb") as f:
            d = pickle.load(f)
        return cls(d["chunk_ids"], d["documents"], d["bm25"])


def build_bm25_index(chunks: List[dict]) -> BM25Index:
    """Build a BM25Okapi index from a list of chunk dicts ({id, text, metadata})."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        raise RuntimeError(
            "rank-bm25 is not installed. Run: pip install -r requirements-ml.txt"
        ) from exc

    ids = [c["id"] for c in chunks]
    docs = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(docs) if docs else None
    logger.info("bm25_built", extra={"n_docs": len(ids)})
    return BM25Index(chunk_ids=ids, documents=docs, bm25=bm25)
