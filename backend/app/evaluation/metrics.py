"""
Deterministic heuristic metrics — no LLM required.

These are the always-available fallback used when DeepEval / LLM-judge can't
run (no API key, library missing, etc.). They are intentionally simple but
correlate well with human judgement on grounded grid-domain answers.

Metric names (all in [0, 1], higher is better):
  - faithfulness        — answer words that appear in retrieved evidence
  - contextual_precision— how much of the retrieved context is used
  - answer_coverage     — recommendations × evidence overlap
  - format_correctness  — required fields present + types correct
  - hallucination_risk  — 1 - faithfulness (legacy name kept for the panel)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_TOKEN = re.compile(r"[a-z][a-z0-9-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "are", "was", "were", "this",
    "that", "have", "has", "but", "not", "you", "your", "our", "their", "they",
    "been", "will", "can", "shall", "should", "would", "could", "any", "all",
    "use", "used", "may", "due", "must", "over", "than", "then", "such", "some",
    "more", "most", "very", "also", "into", "out", "off",
}


def _tok(text: str) -> set:
    return set(t for t in _TOKEN.findall((text or "").lower()) if t not in _STOPWORDS)


def faithfulness(answer: str, retrieved: List[Dict[str, Any]]) -> float:
    """Fraction of answer tokens present in any retrieved chunk."""
    ans_tokens = _tok(answer)
    if not ans_tokens:
        return 0.0
    ctx_tokens = set()
    for c in retrieved or []:
        ctx_tokens |= _tok(c.get("text", ""))
    if not ctx_tokens:
        return 0.0
    overlap = ans_tokens & ctx_tokens
    return round(len(overlap) / max(1, len(ans_tokens)), 3)


def contextual_precision(answer: str, retrieved: List[Dict[str, Any]]) -> float:
    """Fraction of retrieved chunks that share content with the answer."""
    if not retrieved:
        return 0.0
    ans_tokens = _tok(answer)
    if not ans_tokens:
        return 0.0
    used = 0
    for c in retrieved:
        if _tok(c.get("text", "")) & ans_tokens:
            used += 1
    return round(used / len(retrieved), 3)


def answer_coverage(causes: List[Dict], recs: List[Dict]) -> float:
    """Reward responses that produce both causes and recommendations."""
    has_causes = bool(causes)
    has_recs   = bool(recs)
    if has_causes and has_recs:
        return 1.0
    if has_causes or has_recs:
        return 0.5
    return 0.0


def format_correctness(payload: Dict[str, Any]) -> float:
    """Schema sanity check — high signal, almost free."""
    required = ["answer", "root_causes", "recommendations", "confidence"]
    present = sum(1 for k in required if k in payload)
    type_ok = (
        isinstance(payload.get("answer", ""), str)
        and isinstance(payload.get("root_causes", []), list)
        and isinstance(payload.get("recommendations", []), list)
        and isinstance(payload.get("confidence", 0), (int, float))
    )
    return round(0.5 * (present / len(required)) + 0.5 * (1.0 if type_ok else 0.0), 3)


def hallucination_risk(faith: float) -> float:
    return round(max(0.0, 1.0 - faith), 3)


def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run all heuristic metrics on one /analyze response."""
    retrieved = payload.get("retrieved", []) or []
    answer = payload.get("answer", "") or ""
    causes = payload.get("root_causes", []) or []
    recs   = payload.get("recommendations", []) or []

    faith = faithfulness(answer, retrieved)
    return {
        "faithfulness":         faith,
        "contextual_precision": contextual_precision(answer, retrieved),
        "answer_coverage":      answer_coverage(causes, recs),
        "format_correctness":   format_correctness(payload),
        "hallucination_risk":   hallucination_risk(faith),
        "n_retrieved":          len(retrieved),
        "n_causes":             len(causes),
        "n_recommendations":    len(recs),
    }
