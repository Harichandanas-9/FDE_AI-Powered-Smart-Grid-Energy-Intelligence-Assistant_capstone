"""
DeepEval wrapper — runs DeepEval metrics when available, else heuristic fallback.

When DeepEval is installed AND an LLM key is configured (via llm_router),
runs FaithfulnessMetric, AnswerRelevancyMetric, ContextualRelevancyMetric.
Otherwise returns deterministic heuristic scores under the same keys.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.evaluation import metrics as heur

logger = get_logger(__name__)


def _try_deepeval(query: str, answer: str, contexts: List[str]) -> Dict[str, float] | None:
    """Try to run DeepEval metrics. Returns None on any failure."""
    try:
        from deepeval.metrics import (
            FaithfulnessMetric, AnswerRelevancyMetric, ContextualRelevancyMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return None

    try:
        case = LLMTestCase(input=query, actual_output=answer, retrieval_context=contexts)
        out: Dict[str, float] = {}
        for name, Cls in [
            ("faithfulness",         FaithfulnessMetric),
            ("answer_relevancy",     AnswerRelevancyMetric),
            ("contextual_relevancy", ContextualRelevancyMetric),
        ]:
            try:
                m = Cls(threshold=0.5)
                m.measure(case)
                out[name] = round(float(getattr(m, "score", 0) or 0), 3)
            except Exception as exc:
                logger.warning("deepeval_metric_failed",
                               extra={"metric": name, "err": str(exc)})
        return out or None
    except Exception as exc:
        logger.warning("deepeval_run_failed", extra={"err": str(exc)})
        return None


def _has_llm() -> bool:
    """True if at least one LLM key is configured."""
    try:
        s = get_settings()
        return bool(
            s.groq_api_key.strip() or
            s.openai_api_key.strip() or
            getattr(s, "anthropic_api_key", "").strip() or
            getattr(s, "gemini_api_key", "").strip()
        )
    except Exception:
        return False


def run(query: str, payload: Dict[str, Any],
        settings: Settings | None = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    answer   = payload.get("answer") or ""
    contexts = [c.get("text", "") for c in (payload.get("retrieved") or [])]
    h        = heur.evaluate(payload)

    # Only attempt DeepEval when an LLM key is present
    deep = _try_deepeval(query, answer, contexts) if _has_llm() else None

    if deep is None:
        return {
            "provider":              "heuristic",
            "faithfulness":          h["faithfulness"],
            "answer_relevancy":      h["contextual_precision"],
            "contextual_relevancy":  h["contextual_precision"],
            "hallucination_risk":    h["hallucination_risk"],
            "format_correctness":    h["format_correctness"],
            "answer_coverage":       h["answer_coverage"],
            "_heuristic_only":       True,
        }

    return {
        "provider":            "deepeval",
        **deep,
        "hallucination_risk":  round(1 - deep.get("faithfulness", 0), 3),
        "format_correctness":  h["format_correctness"],
        "answer_coverage":     h["answer_coverage"],
        "_heuristic_only":     False,
    }
