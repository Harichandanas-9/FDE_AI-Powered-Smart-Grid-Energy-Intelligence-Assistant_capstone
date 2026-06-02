"""
Hybrid retrieval = semantic (Chroma) + keyword (BM25), fused with
Reciprocal Rank Fusion.

RRF rationale
-------------
Different rankers return scores on different scales (Chroma cosine ∈ [0,1],
BM25 typically 0–30). Normalizing then summing is fragile. RRF uses RANKS:

    score(doc) = sum over rankers of (weight / (k + rank_in_ranker))

with k=60 (standard). Higher = better. This is the same fusion strategy
used by major IR competitions (TREC).

Public entry point
------------------
    HybridRetriever(settings, bm25_index).retrieve(
        query, top_k, where=None
    ) -> list[RetrievedChunk]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.rag.bm25_index import BM25Index
from app.rag.embeddings import embed_query
from app.rag.vector_store import get_client, get_or_create_collection, query_collection

logger = get_logger(__name__)

RRF_K = 60


@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float            # fused RRF score
    semantic_rank: Optional[int] = None
    keyword_rank: Optional[int] = None


def _rrf(ranked_list: List[str], weight: float) -> Dict[str, float]:
    """Convert a ranked list of ids into RRF contributions."""
    return {cid: weight / (RRF_K + rank) for rank, cid in enumerate(ranked_list, start=1)}


class HybridRetriever:
    def __init__(self, settings: Settings, bm25_index: Optional[BM25Index] = None):
        self.settings = settings
        self.bm25 = bm25_index
        self._chroma_collection = None  # lazy

    def _collection(self):
        if self._chroma_collection is None:
            client = get_client(self.settings.chroma_persist_dir)
            self._chroma_collection = get_or_create_collection(client)
        return self._chroma_collection

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = None,
        where: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        top_k = top_k or self.settings.final_top_k
        candidates = self.settings.retrieval_top_k

        # Tenant filter: prefer the caller's tenant, also include "default"
        # tenant chunks so cross-tenant baseline data (if any) is visible.
        if tenant_id and tenant_id != "default":
            tenant_where = {"$or": [
                {"tenant_id": tenant_id},
                {"tenant_id": "default"},
            ]}
            if where:
                # Chroma supports $and at the top level
                where = {"$and": [where, tenant_where]}
            else:
                where = tenant_where

        # --- 1. Semantic search via Chroma ---
        # SAFETY: Only open ChromaDB if already initialised (via /embed).
        # On Windows + Python 3.13 + ChromaDB 1.5.9, the first open from
        # /analyze can crash the worker. /embed is the designated init path.
        sem_ids: List[str] = []
        sem_docs: Dict[str, str] = {}
        sem_meta: Dict[str, Dict] = {}
        try:
            from app.rag.vector_store import _CLIENT as _chroma_client
            if _chroma_client is not None:
                q_emb = embed_query(query, model_name=self.settings.embedding_model)
                sem_res = query_collection(
                    self._collection(), q_emb, top_k=candidates, where=where
                )
                sem_ids = sem_res.get("ids", [[]])[0]
                for i, cid in enumerate(sem_ids):
                    sem_docs[cid] = sem_res.get("documents", [[]])[0][i]
                    sem_meta[cid] = sem_res.get("metadatas", [[]])[0][i]
            else:
                logger.info("semantic_search_skipped_chroma_not_initialized")
        except Exception as exc:  # noqa: BLE001 — fall back to keyword-only
            logger.warning("semantic_retrieval_failed", extra={"err": str(exc)})

        # --- 2. Keyword search via BM25 ---
        kw_ranked: List[tuple] = []
        if self.bm25 is not None:
            kw_ranked = self.bm25.search(query, top_k=candidates)

        # --- 3. RRF fusion ---
        sem_scores = _rrf(sem_ids, weight=self.settings.rrf_semantic_weight)
        kw_scores = _rrf(
            [cid for cid, _ in kw_ranked], weight=self.settings.rrf_keyword_weight
        )
        all_ids = set(sem_scores) | set(kw_scores)
        fused = {cid: sem_scores.get(cid, 0) + kw_scores.get(cid, 0) for cid in all_ids}

        # --- 4. Apply post-filter `where` for BM25-only hits without metadata ---
        # (Chroma hits already filtered; BM25 needs explicit check)
        if where:
            def _meta_ok(cid: str) -> bool:
                m = sem_meta.get(cid)
                if m is None:
                    return True  # we can't filter BM25 hits without metadata; allow
                for k, v in where.items():
                    if m.get(k) != v:
                        return False
                return True
            fused = {cid: s for cid, s in fused.items() if _meta_ok(cid)}

        # --- 5. Build RetrievedChunk results ---
        ordered = sorted(fused.items(), key=lambda x: -x[1])[:top_k]
        rank_sem = {cid: r for r, cid in enumerate(sem_ids, start=1)}
        kw_ids_only = [cid for cid, _ in kw_ranked]
        rank_kw = {cid: r for r, cid in enumerate(kw_ids_only, start=1)}

        results = []
        for cid, score in ordered:
            results.append(
                RetrievedChunk(
                    id=cid,
                    text=sem_docs.get(cid, ""),
                    metadata=sem_meta.get(cid, {}),
                    score=round(score, 6),
                    semantic_rank=rank_sem.get(cid),
                    keyword_rank=rank_kw.get(cid),
                )
            )
        logger.info(
            "hybrid_retrieved",
            extra={"query_len": len(query), "n_semantic": len(sem_ids),
                   "n_keyword": len(kw_ranked), "n_returned": len(results)},
        )
        # --- 6. Optional cross-encoder reranking ---
        if self.settings.reranker_enabled and results:
            try:
                from app.rag.reranker import rerank
                results = rerank(
                    query, results,
                    model_name=self.settings.reranker_model,
                    top_k=top_k,
                )
                logger.info("reranked", extra={"n": len(results)})
            except Exception as exc:  # noqa: BLE001
                logger.warning("reranker_skipped", extra={"err": str(exc)})


        # --- 7. CRAG: retry with reformulated query if top score is too low ---
        crag_threshold = getattr(self.settings, "crag_relevance_threshold", 0.0)
        if crag_threshold > 0 and results:
            max_score = max(r.score for r in results)
            if max_score < crag_threshold:
                try:
                    new_q = self._reformulate_query(query)
                    if new_q and new_q.lower() != query.lower():
                        logger.info("crag_retry",
                                    extra={"original": query, "reformulated": new_q,
                                           "score": max_score})
                        results2 = self.retrieve(new_q, top_k=top_k, where=where,
                                                  tenant_id=tenant_id)
                        if results2 and max(r.score for r in results2) > max_score:
                            results = results2
                except Exception as exc:
                    logger.warning("crag_reformulate_failed", extra={"err": str(exc)})

        return results

    _REFORMULATE_SYSTEM = (
        "You rewrite smart-grid energy queries to improve retrieval. "
        "Output ONE alternative query using different but related grid/power terminology. "
        "Return only the rewritten query, no preamble, no quotes."
    )

    def _reformulate_query(self, query: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.core.llm_router import TaskType, router as llm_router
        msgs = [
            SystemMessage(content=self._REFORMULATE_SYSTEM),
            HumanMessage(content=f"Original: {query}\nRewritten:"),
        ]
        resp = llm_router.invoke(TaskType.ROUTING, msgs)
        return (getattr(resp, "content", "") or "").strip().strip('"').strip("'")
