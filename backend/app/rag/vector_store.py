"""
ChromaDB persistent vector store — hardened for ChromaDB 1.x compatibility.

ChromaDB 1.x rejects:
  - None values in metadata
  - Empty metadata dicts ({})
  - Non-primitive types in metadata (list, dict, etc.)

This wrapper sanitizes all metadata before upsert and surfaces clear errors
when something goes wrong.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "grid_incidents"
_CLIENT = None
_LOCK = Lock()


def _import_chroma():
    try:
        import chromadb
        try:
            from chromadb.config import Settings as ChromaSettings
        except Exception:
            ChromaSettings = None
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is not installed. Run: pip install chromadb"
        ) from exc
    return chromadb, ChromaSettings


def get_client(persist_dir: str):
    """Return a singleton persistent client. Creates the directory if needed.

    Works on ChromaDB 0.5.x and 1.x.
    """
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    with _LOCK:
        if _CLIENT is None:
            chromadb, ChromaSettings = _import_chroma()
            from app.utils.paths import resolve_dir
            resolved = resolve_dir(persist_dir, create=True)
            # Try with Settings, fall back to no Settings for newer Chroma
            try:
                if ChromaSettings is not None:
                    _CLIENT = chromadb.PersistentClient(
                        path=str(resolved),
                        settings=ChromaSettings(anonymized_telemetry=False),
                    )
                else:
                    _CLIENT = chromadb.PersistentClient(path=str(resolved))
            except Exception as exc:  # noqa: BLE001
                logger.warning("chroma_client_with_settings_failed_retry_plain",
                               extra={"err": str(exc)})
                _CLIENT = chromadb.PersistentClient(path=str(resolved))
            logger.info("chroma_client_ready",
                        extra={"path": str(resolved.resolve()),
                               "chromadb_version": getattr(chromadb, "__version__", "?")})
    return _CLIENT


def get_or_create_collection(client, name: str = COLLECTION_NAME):
    """Return the collection, creating it with cosine distance if absent.

    Some ChromaDB 1.x setups reject the metadata kw; we retry without it.
    """
    try:
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_or_create_with_metadata_failed_retry_plain",
                       extra={"err": str(exc)})
        return client.get_or_create_collection(name=name)


# ---------------------------------------------------------------------------
def _sanitize_one(m: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB 1.x metadata rules:
      - values must be str | int | float | bool
      - no None values
      - no empty dicts

    We drop None, coerce other types to str, and inject a placeholder field
    if the dict ends up empty so Chroma doesn't reject it.
    """
    clean: Dict[str, Any] = {}
    for k, v in (m or {}).items():
        if v is None:
            continue
        if isinstance(v, bool) or isinstance(v, (int, float, str)):
            clean[k] = v
        else:
            # Lists/dicts/datetimes — coerce to string so we keep some info
            try:
                clean[k] = str(v)
            except Exception:
                continue
    if not clean:
        clean = {"_placeholder": "1"}
    return clean


def upsert_chunks(
    collection,
    ids: List[str],
    texts: List[str],
    embeddings: np.ndarray,
    metadatas: List[Dict[str, Any]],
) -> int:
    """Idempotent upsert. Returns total collection count after upsert."""
    if not ids:
        return collection.count()

    sanitized = [_sanitize_one(m) for m in metadatas]

    # Embeddings can be ndarray or list-of-list
    if hasattr(embeddings, "tolist"):
        emb_list = embeddings.tolist()
    else:
        emb_list = list(embeddings)

    try:
        collection.upsert(
            ids=list(ids),
            documents=list(texts),
            embeddings=emb_list,
            metadatas=sanitized,
        )
    except Exception as exc:
        logger.exception("chroma_upsert_failed",
                         extra={"n_items": len(ids),
                                "sample_metadata": sanitized[0] if sanitized else None})
        raise

    return collection.count()


def query_collection(
    collection,
    query_embedding: np.ndarray,
    *,
    top_k: int = 10,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Semantic search. Returns Chroma's native result dict."""
    q = query_embedding.tolist() if hasattr(query_embedding, "tolist") else list(query_embedding)
    try:
        return collection.query(
            query_embeddings=[q],
            n_results=top_k,
            where=where,
        )
    except Exception as exc:
        logger.warning("chroma_query_failed_retry_without_where",
                       extra={"err": str(exc), "where": where})
        # Some Chroma versions reject complex where clauses — retry without
        return collection.query(query_embeddings=[q], n_results=top_k)


def count(collection) -> int:
    try:
        return collection.count()
    except Exception:
        return 0


def reset_collection(client, name: str = COLLECTION_NAME) -> None:
    """Drop and recreate the collection. Use this when re-ingesting from scratch."""
    try:
        client.delete_collection(name)
        logger.info("collection_deleted", extra={"name": name})
    except Exception:
        pass
    get_or_create_collection(client, name)
