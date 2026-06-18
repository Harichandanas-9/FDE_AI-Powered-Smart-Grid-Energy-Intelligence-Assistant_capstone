"""
Base agent abstract class + the shared envelope.

Every agent reads from and writes to one envelope dict. This keeps A2A
communication explicit and observable: the orchestrator can log every
agent's contribution, and the response carries a full `agent_trace` for
the UI's multi-agent visualization.

Envelope schema (cumulative; each agent fills its section):
{
    "query": str,                     # original
    "masked_query": str,              # after guardrails
    "tenant_id": str,
    "filters": {region, severity, source} | {},
    "guardrail": {...},               # GuardrailVerdict.to_dict()
    "retrieved": [chunk_dict, ...],   # filled by RetrievalAgent
    "stability_analysis": {...},      # filled by StabilityAgent
    "root_causes": [...],             # filled by FailureAgent
    "answer": str,                    # filled by RecommendationAgent
    "recommendations": [...],         # filled by RecommendationAgent
    "confidence": float,              # filled by RecommendationAgent
    "reasoning": str,                 # filled by RecommendationAgent
    "agent_trace": [
        {"agent": str, "status": "ok|error|skipped", "duration_ms": float,
         "summary": str, "error": str|None}
    ],
}
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Subclasses set a `name` and implement `_run(envelope)`."""

    name: str = "base"

    def __init__(self, settings: Settings):
        """Store application settings for use by concrete agent implementations."""
        self.settings = settings

    def execute(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Wraps `_run` with timing + trace recording + error swallowing."""
        t0 = time.time()
        summary, status, error = "", "ok", None
        try:
            envelope, summary = self._run(envelope)
        except Exception as exc:  # noqa: BLE001 — agents must never crash the chain
            status, error = "error", f"{exc.__class__.__name__}: {exc}"
            logger.exception("agent_failed", extra={"agent": self.name})
        finally:
            duration_ms = round((time.time() - t0) * 1000, 1)
            envelope.setdefault("agent_trace", []).append(
                {
                    "agent": self.name,
                    "status": status,
                    "duration_ms": duration_ms,
                    "summary": summary,
                    "error": error,
                }
            )
        return envelope

    @abstractmethod
    def _run(self, envelope: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """Return (updated envelope, short human summary for the trace)."""
        ...
