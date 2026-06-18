"""
LLM-as-judge for mitigation quality.

Uses the llm_router (supports Groq, OpenAI, Anthropic) to score the /analyze
response on accuracy, completeness, and actionability.
Falls back to heuristic scoring when no LLM is configured.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.evaluation import metrics as heur

logger = get_logger(__name__)

JUDGE_PROMPT = """You are an impartial evaluator for a smart-grid AI assistant.
Grade the following AI response to an operator query.

Operator query: {query}

AI response (JSON):
{response_json}

Score each dimension on a 1-5 integer scale and respond with ONLY this JSON:
{{
  "accuracy":     <1-5>,
  "completeness": <1-5>,
  "actionability":<1-5>,
  "rationale": "<one sentence>"
}}"""


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert 1-5 integer judge scores to [0, 1] floats."""
    def n(v):
        try:
            return max(0.0, min(1.0, (float(v) - 1) / 4))
        except (TypeError, ValueError):
            return 0.0
    return {
        "accuracy":      n(raw.get("accuracy", 3)),
        "completeness":  n(raw.get("completeness", 3)),
        "actionability": n(raw.get("actionability", 3)),
        "rationale":     str(raw.get("rationale", ""))[:300],
        "provider":      "llm_router",
    }


def _heuristic_judge(query: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute judge scores deterministically from heuristic metrics when no LLM is available."""
    h = heur.evaluate(payload)
    return {
        "accuracy":      h["faithfulness"],
        "completeness":  h["answer_coverage"],
        "actionability": min(1.0, 0.2 + 0.2 * h["n_recommendations"]),
        "rationale":     (f"Heuristic: faithfulness={h['faithfulness']:.2f}, "
                          f"causes={h['n_causes']}, recs={h['n_recommendations']}"),
        "provider":      "heuristic",
    }


def judge(query: str, payload: Dict[str, Any],
          settings: Settings | None = None) -> Dict[str, Any]:
    """Score an /analyze response on accuracy, completeness, and actionability.

    Uses the LLM router when an API key is present; falls back to heuristic
    scoring silently on any LLM failure.
    """
    settings = settings or get_settings()

    slim = {
        "answer":           payload.get("answer"),
        "root_causes":      payload.get("root_causes"),
        "recommendations":  payload.get("recommendations"),
        "confidence":       payload.get("confidence"),
        "retrieved_ids":    [c.get("id") for c in (payload.get("retrieved") or [])][:5],
    }
    prompt = JUDGE_PROMPT.format(query=query[:300], response_json=json.dumps(slim))

    # Use llm_router — works with Groq, OpenAI, Anthropic, Gemini
    try:
        from app.core.llm_router import TaskType, router as llm_router
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = [
            SystemMessage(content="Respond with valid JSON only. No markdown fences."),
            HumanMessage(content=prompt),
        ]
        resp = llm_router.invoke(TaskType.ANALYSIS, msgs)
        text = getattr(resp, "content", "") or ""
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            raw = json.loads(text[start:end + 1])
            return _normalize(raw)
    except Exception as exc:
        logger.warning("llm_judge_failed_fallback", extra={"err": str(exc)})

    return _heuristic_judge(query, payload)
