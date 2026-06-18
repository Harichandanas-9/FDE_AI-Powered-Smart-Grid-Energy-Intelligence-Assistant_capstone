"""
Full RAG pipeline — the brain of /analyze.

Pipeline:
  query --> guardrails --> hybrid retrieve --> (optional rerank)
        --> prompt --> LLM (or template fallback) --> JSON-validate
        --> return structured AnalyzeResponse payload
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.bm25_index import BM25Index
from app.rag.hybrid_retriever import HybridRetriever, RetrievedChunk
from app.rag.llm import TemplateProvider, get_provider
from app.utils.guardrails import GuardrailVerdict, validate_query

logger = get_logger(__name__)


def _chunk_to_dict(c: RetrievedChunk) -> Dict[str, Any]:
    """Serialize a RetrievedChunk to a plain dict suitable for JSON responses."""
    return {
        "id": c.id,
        "text": c.text,
        "metadata": c.metadata,
        "score": c.score,
        "semantic_rank": c.semantic_rank,
        "keyword_rank": c.keyword_rank,
    }


class RagPipeline:
    """Orchestrates the full RAG pipeline: guardrails -> retrieve -> generate -> validate."""

    def __init__(self, settings: Optional[Settings] = None,
                 bm25_index: Optional[BM25Index] = None):
        """Wire up the retriever and LLM provider from settings."""
        self.settings = settings or get_settings()
        self.retriever = HybridRetriever(self.settings, bm25_index=bm25_index)
        self.provider = get_provider(self.settings)
        logger.info(
            "rag_pipeline_ready",
            extra={"provider": self.provider.name,
                   "embedding_model": self.settings.embedding_model},
        )

    # ----------------------------------------------------------------------
    def run(self, query: str, *, where: Optional[Dict[str, Any]] = None,
            top_k: Optional[int] = None,
            tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the end-to-end RAG pipeline for a single query.

        Validates the query through guardrails, retrieves relevant chunks,
        generates a structured answer, and returns the full response payload.
        Automatically falls back to TemplateProvider if the primary LLM fails.
        """
        t0 = time.time()

        # 1) Guardrails
        verdict: GuardrailVerdict = validate_query(query)
        if not verdict.allow:
            return {
                "status": "refused",
                "guardrail": verdict.to_dict(),
                "answer": verdict.response_message,
                "duration_seconds": round(time.time() - t0, 3),
                "provider": self.provider.name,
                "retrieved": [],
                "root_causes": [],
                "recommendations": [],
                "confidence": 0.0,
                "reasoning": "",
                "tenant_id": tenant_id or "default",
            }

        masked = verdict.masked_query

        # 2) Retrieve
        chunks = self.retriever.retrieve(masked, top_k=top_k, where=where,
                                          tenant_id=tenant_id)

        # 3) Generate (LLM or template fallback)
        try:
            raw = self.provider.generate(masked, chunks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_generate_failed_fallback",
                           extra={"err": str(exc), "provider": self.provider.name})
            raw = TemplateProvider().generate(masked, chunks)
            self_provider_name = f"{self.provider.name}->template_fallback"
        else:
            self_provider_name = self.provider.name

        # 4) Validate / coerce JSON shape
        raw = _coerce_shape(raw)

        return {
            "status": "ok",
            "guardrail": verdict.to_dict(),
            "query": query,
            "masked_query": masked,
            "answer": raw["answer"],
            "root_causes": raw["root_causes"],
            "recommendations": raw["recommendations"],
            "confidence": raw["confidence"],
            "reasoning": raw["reasoning"],
            "retrieved": [_chunk_to_dict(c) for c in chunks],
            "provider": self_provider_name,
            "duration_seconds": round(time.time() - t0, 3),
            "tenant_id": tenant_id or "default",
        }


# --------------------------------------------------------------------------- #
# Defensive shape coercion: an LLM may omit keys or supply wrong types.
# We never trust the LLM blindly.

def _coerce_shape(d: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the LLM response dict has all required keys with correct types.

    Replaces missing or wrong-typed fields with safe defaults so downstream
    Pydantic validation never fails due to an unexpected LLM output.
    """
    def _s(x, default=""):
        return x if isinstance(x, str) else default
    def _l(x):
        return x if isinstance(x, list) else []
    def _f(x, default=0.0):
        try: return float(x)
        except Exception: return default

    return {
        "answer": _s(d.get("answer"), ""),
        "root_causes": [
            {
                "cause": _s(rc.get("cause") if isinstance(rc, dict) else "", ""),
                "probability": _f(rc.get("probability") if isinstance(rc, dict) else 0),
                "evidence": _l(rc.get("evidence") if isinstance(rc, dict) else []),
            }
            for rc in _l(d.get("root_causes"))
        ],
        "recommendations": [
            {
                "action": _s(r.get("action") if isinstance(r, dict) else "", ""),
                "priority": _s(r.get("priority") if isinstance(r, dict) else "medium", "medium"),
                "rationale": _s(r.get("rationale") if isinstance(r, dict) else "", ""),
            }
            for r in _l(d.get("recommendations"))
        ],
        "confidence": max(0.0, min(1.0, _f(d.get("confidence"), 0.5))),
        "reasoning": _s(d.get("reasoning"), ""),
    }
