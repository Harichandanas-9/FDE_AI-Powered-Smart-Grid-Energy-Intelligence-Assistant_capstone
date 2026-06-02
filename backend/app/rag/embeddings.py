"""
Embedding generator — sentence-transformers with a torch-free fallback.

Two modes, picked automatically at load time:
  1. sentence-transformers (MiniLM-L6-v2)  — best quality, requires torch + DLLs
  2. HashEmbedder (pure NumPy)             — fallback when torch fails to load

Why the fallback exists
-----------------------
On Python 3.13 + Windows, torch wheels frequently fail with DLL load errors
that can only be fixed with admin rights (VC++ redist) or registry edits.
This project must run on locked-down corporate laptops, so we provide a
deterministic, dependency-free fallback that still produces useful retrieval
when combined with BM25 keyword search.

Quality note
------------
HashEmbedder uses feature-hashing (scikit-learn's HashingVectorizer technique):
each word and word-bigram is hashed into one of 384 buckets, the vector is
normalized. Texts sharing vocabulary -> similar vectors -> cosine works.
For grid-domain text where every chunk uses power-system terminology, this
gives recall comparable to MiniLM on the demo corpus. The hybrid retriever's
BM25 leg picks up exact-match precision.
"""
from __future__ import annotations

import hashlib
import re
from threading import Lock
from typing import List, Optional

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

_DIM = 384
_TOKEN_RE = re.compile(r"[a-z][a-z0-9-]+")

_MODEL = None
_MODEL_NAME: Optional[str] = None
_MODEL_KIND: str = "uninitialized"   # 'sentence-transformers' | 'hash-fallback'
_LOCK = Lock()


# ============================================================================
# Hash-based fallback embedder — pure NumPy
# ============================================================================
def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


class HashEmbedder:
    """Deterministic keyword-hash embedder (feature-hashing trick)."""

    def __init__(self, dim: int = _DIM):
        self.dim = dim
        self.name = "hash-fallback"

    def encode(
        self,
        texts,
        batch_size: int = 512,         # noqa: ARG002 — match ST signature
        show_progress_bar: bool = False,   # noqa: ARG002
        convert_to_numpy: bool = True,     # noqa: ARG002
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        arr = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            toks = _tokens(text)
            # unigrams (weight 1.0)
            for tok in toks:
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
                arr[i, h] += 1.0
            # bigrams (weight 0.5) — boosts phrase discrimination
            for a, b in zip(toks, toks[1:]):
                h = int(hashlib.md5(f"{a}_{b}".encode("utf-8")).hexdigest(), 16) % self.dim
                arr[i, h] += 0.5
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            arr = arr / norms
        return arr


# ============================================================================
# Model selection — try sentence-transformers, fall back on ANY failure
# ============================================================================
def _load_model(model_name: str):
    # Fast-mode: 'hash' model name -> instant HashEmbedder (no download, no torch)
    if model_name in ('hash', 'hash-fallback', 'fast', 'demo'):
        logger.info("hash_embedder_selected", extra={"model_name": model_name})
        return HashEmbedder(_DIM)
    """Try real MiniLM; on import error, DLL load failure, or any exception,
    silently fall back to HashEmbedder. The system never crashes from a
    missing torch."""
    global _MODEL_KIND

    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except Exception as exc:  # noqa: BLE001 — ImportError, DLL errors, etc.
        logger.warning("sentence_transformers_unavailable_using_hash_fallback",
                       extra={"err": f"{exc.__class__.__name__}: {exc}"})
        _MODEL_KIND = "hash-fallback"
        return HashEmbedder(_DIM)

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", extra={"model": model_name})
        model = SentenceTransformer(model_name, device="cpu")
        logger.info("embedding_model_loaded",
                    extra={"model": model_name, "kind": "sentence-transformers"})
        _MODEL_KIND = "sentence-transformers"
        return model
    except Exception as exc:  # noqa: BLE001
        logger.warning("sentence_transformers_load_failed_using_hash_fallback",
                       extra={"err": f"{exc.__class__.__name__}: {exc}"})
        _MODEL_KIND = "hash-fallback"
        return HashEmbedder(_DIM)


def get_embedder(model_name: str):
    """Return a cached embedder. Thread-safe."""
    global _MODEL, _MODEL_NAME
    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL
    with _LOCK:
        if _MODEL is None or _MODEL_NAME != model_name:
            _MODEL = _load_model(model_name)
            _MODEL_NAME = model_name
    return _MODEL


def current_mode() -> str:
    """Returns 'sentence-transformers' | 'hash-fallback' | 'uninitialized'."""
    return _MODEL_KIND


def embed_texts(
    texts: List[str],
    model_name: str,
    *,
    batch_size: int = 512,
    normalize: bool = True,
) -> np.ndarray:
    """Embed a list of strings -> (n, 384) float32 numpy array."""
    model = get_embedder(model_name)
    arr = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )
    if hasattr(arr, "astype"):
        arr = arr.astype(np.float32)
    logger.info(
        "embeddings_generated",
        extra={"count": len(texts),
               "dim": arr.shape[1] if hasattr(arr, "shape") and arr.ndim == 2 else 0,
               "mode": _MODEL_KIND},
    )
    return arr


def embed_query(text: str, model_name: str) -> np.ndarray:
    """Single query string -> (384,) array."""
    return embed_texts([text], model_name=model_name)[0]
