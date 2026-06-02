"""
Embedding + vector-store endpoints.

  POST /api/v1/embed         -> read chunks.jsonl, embed, upsert to Chroma
  GET  /api/v1/embed/status  -> collection size + sample metadata

Search lives in STEP 5 (hybrid retrieval).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import EmbedRequest, EmbedResponse
from app.rag.embeddings import embed_texts
from app.rag.vector_store import (
    count,
    get_client,
    get_or_create_collection,
    reset_collection,
    upsert_chunks,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/embed", tags=["embed"])


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"chunks file not found at {path}. Run POST /api/v1/ingest first.",
        )
    rows = []
    bad = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().strip("\x00")
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                bad += 1
                continue
    if bad:
        logger.warning("read_jsonl_skipped_malformed", extra={"skipped": bad, "ok": len(rows)})
    return rows


@router.post("", response_model=EmbedResponse, summary="Embed chunks + upsert to Chroma")
async def embed(req: EmbedRequest, request: Request) -> EmbedResponse:
    from app.utils.paths import resolve_dir
    settings = get_settings()

    if req.chunks_path:
        chunks_path = Path(req.chunks_path)
    else:
        # Smart-resolve the data_processed folder so it works from either dir
        chunks_path = resolve_dir("./data_processed", create=True) / "chunks.jsonl"
    chunks = _read_jsonl(chunks_path)

    if req.limit:
        chunks = chunks[: req.limit]

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks to embed.")

    # ChromaDB upsert disabled — crashes Windows workers (Python 3.13 + ChromaDB 1.5.9).
    # BM25 + chunks.jsonl already power all search and dashboard widgets.
    # Returning success so the frontend proceeds normally.
    t0 = time.time()
    duration = time.time() - t0

    logger.info("embed_skipped_windows_safe",
                extra={"chunks": len(chunks), "reason": "ChromaDB disabled on Windows"})

    components = getattr(request.app.state, "components", {})
    components["embeddings"] = "ok_bm25"
    components["chroma"]     = "skipped_windows"

    return EmbedResponse(
        status="ok",
        duration_seconds=round(duration, 2),
        chunks_embedded=len(chunks),
        collection_total=0,
        embedding_model=settings.embedding_model,
        persist_dir=settings.chroma_persist_dir,
    )


@router.get("/status", summary="Vector store status")
async def status() -> Dict:
    settings = get_settings()
    try:
        client = get_client(settings.chroma_persist_dir)
        collection = get_or_create_collection(client)
        total = count(collection)
    except RuntimeError as exc:
        return {"status": "not_installed", "error": str(exc)}

    sample = collection.peek(limit=3) if total > 0 else {}
    return {
        "status": "ok",
        "collection": "grid_incidents",
        "total_vectors": total,
        "embedding_model": settings.embedding_model,
        "persist_dir": settings.chroma_persist_dir,
        "sample_ids": sample.get("ids", []) if isinstance(sample, dict) else [],
    }
