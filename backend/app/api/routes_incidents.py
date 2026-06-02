"""
GET /api/v1/incidents — list / search historical incidents.

Supports:
  ?q=...           hybrid search (semantic + BM25 + RRF)
  ?region=...      metadata filter
  ?severity=...    metadata filter
  ?source=...      metadata filter (stability | household | consumption)
  ?limit=N         max results to return

Tenant isolation: chunks whose tenant_id doesn't match the caller's tenant
(and aren't the shared "default" tenant) are excluded.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import get_settings
from app.core.security import get_current_principal
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.vector_store import get_client, get_or_create_collection

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _tenant_filter(tenant_id: str, where: Dict[str, Any]) -> Dict[str, Any]:
    if tenant_id == "default":
        return where
    tenant_where = {"$or": [
        {"tenant_id": tenant_id},
        {"tenant_id": "default"},
    ]}
    if where:
        return {"$and": [where, tenant_where]}
    return tenant_where


@router.get("", summary="List or search incidents")
async def list_incidents(
    request: Request,
    principal: dict = Depends(get_current_principal),
    q: Optional[str] = Query(default=None, description="Hybrid query string"),
    region: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> Dict[str, Any]:
    settings = get_settings()
    tenant_id = principal["tenant_id"]

    where: Dict[str, Any] = {}
    if region:   where["region"] = region
    if severity: where["severity"] = severity
    if source:   where["source_dataset"] = source

    # Search mode
    if q:
        bm25 = getattr(request.app.state, "bm25_index", None)
        retr = HybridRetriever(settings, bm25_index=bm25)
        results = retr.retrieve(q, top_k=limit, where=where or None,
                                tenant_id=tenant_id)
        return {
            "mode": "hybrid_search",
            "query": q,
            "filters": where,
            "tenant_id": tenant_id,
            "count": len(results),
            "incidents": [
                {
                    "id": c.id,
                    "text": c.text,
                    "metadata": c.metadata,
                    "score": c.score,
                    "semantic_rank": c.semantic_rank,
                    "keyword_rank": c.keyword_rank,
                }
                for c in results
            ],
        }

    # Browse mode — try Chroma, gracefully fall back to chunks.jsonl
    ids, docs, metas = [], [], []
    try:
        client = get_client(settings.chroma_persist_dir)
        collection = get_or_create_collection(client)
        final_where = _tenant_filter(tenant_id, where)
        if final_where:
            data = collection.get(where=final_where, limit=limit)
        else:
            data = collection.get(limit=limit)
        ids = data.get("ids", []) or []
        docs = data.get("documents", []) or []
        metas = data.get("metadatas", []) or []
    except Exception:
        # ChromaDB unavailable -> offline browse from chunks.jsonl
        import json as _json
        from app.utils.paths import resolve_dir
        try:
            cpath = resolve_dir("./data_processed", create=False) / "chunks.jsonl"
            if cpath.exists():
                with cpath.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ch = _json.loads(line)
                        except Exception:
                            continue
                        m = ch.get("metadata", {}) or {}
                        if where and any(m.get(k) != v for k, v in where.items()):
                            continue
                        t = m.get("tenant_id", "default")
                        if tenant_id != "default" and t not in (tenant_id, "default"):
                            continue
                        ids.append(ch.get("id"))
                        docs.append(ch.get("text", ""))
                        metas.append(m)
                        if len(ids) >= limit:
                            break
        except Exception:
            pass
    return {
        "mode": "browse",
        "filters": where,
        "tenant_id": tenant_id,
        "count": len(ids),
        "incidents": [
            {"id": ids[i], "text": docs[i], "metadata": metas[i]}
            for i in range(len(ids))
        ],
    }
