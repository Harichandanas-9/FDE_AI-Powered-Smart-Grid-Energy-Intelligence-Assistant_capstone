"""
Embedding generator — three-tier fallback for Python 3.11 / corporate laptops.

Load order (picked automatically):
  1. sentence-transformers (all-MiniLM-L6-v2) — best quality; needs torch.
  2. fastembed (BAAI/bge-small-en-v1.5)       — no torch DLLs, ONNX runtime.
  3. HashEmbedder (pure NumPy)                — zero dependencies; last resort.

Why three tiers
---------------
On Python 3.11 + Windows, torch wheels may fail with DLL load errors on
locked-down corporate laptops. fastembed uses ONNX Runtime (no torch), so it
works in those environments with near-MiniLM quality. HashEmbedder is kept as
the final safety net so the app never crashes from a missing model.

FastEmbedWrapper adapts the fastembed API to match the sentence-transformers
.encode() signature so the rest of the codebase stays unchanged.
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
_MODEL_KIND: str = "uninitialized"   # 'sentence-transformers' | 'fastembed' | 'hash-fallback'
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
# fastembed wrapper — adapts TextEmbedding to match the ST .encode() API
# ============================================================================
class FastEmbedWrapper:
    """Wraps fastembed.TextEmbedding to look like a SentenceTransformer."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding  # noqa: PLC0415
        self._model = TextEmbedding(model_name)
        self.name = f"fastembed:{model_name}"

    def encode(
        self,
        texts,
        batch_size: int = 256,           # noqa: ARG002
        show_progress_bar: bool = False,  # noqa: ARG002
        convert_to_numpy: bool = True,    # noqa: ARG002
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        # fastembed returns a generator of np arrays
        vecs = list(self._model.embed(texts))
        arr = np.array(vecs, dtype=np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            arr = arr / norms
        return arr


# ============================================================================
# Model selection — sentence-transformers → fastembed → hash (3-tier)
# ============================================================================
def _load_model(model_name: str):
    global _MODEL_KIND

    # Explicit hash mode — instant, no download
    if model_name in ("hash", "hash-fallback", "fast", "demo"):
        logger.info("hash_embedder_selected", extra={"model_name": model_name})
        _MODEL_KIND = "hash-fallback"
        return HashEmbedder(_DIM)

    # --- Tier 1: sentence-transformers (needs torch) ---
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model",
                    extra={"model": model_name, "tier": "sentence-transformers"})
        model = SentenceTransformer(model_name, device="cpu")
        _MODEL_KIND = "sentence-transformers"
        logger.info("embedding_model_loaded",
                    extra={"model": model_name, "kind": "sentence-transformers"})
        return model
    except Exception as exc:  # noqa: BLE001
        logger.warning("sentence_transformers_failed_trying_fastembed",
                       extra={"err": f"{exc.__class__.__name__}: {exc}"})

    # --- Tier 2: fastembed (ONNX runtime, no torch DLLs) ---
    try:
        fast_model = "BAAI/bge-small-en-v1.5"
        logger.info("loading_fastembed", extra={"model": fast_model})
        wrapper = FastEmbedWrapper(fast_model)
        _MODEL_KIND = "fastembed"
        logger.info("fastembed_loaded", extra={"model": fast_model})
        return wrapper
    except Exception as exc:  # noqa: BLE001
        logger.warning("fastembed_failed_using_hash_fallback",
                       extra={"err": f"{exc.__class__.__name__}: {exc}"})

    # --- Tier 3: HashEmbedder (zero deps) ---
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
