"""Failure Analysis Agent — LangGraph node for root-cause identification."""
from __future__ import annotations

from app.agents._common import node_span, truncate_context
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are the Grid Failure Analysis Agent. Identify probable root cause(s) of the grid issue. "
    "Consider: voltage instability, transformer overload, frequency deviation, reactive power imbalance, "
    "node timing desynchronization, and cascading faults. "
    "Structure: 1) Primary Root Cause, 2) Contributing Factors, 3) Affected Components."
)


def analyze_failure(state: dict) -> dict:
    """LangGraph node: use the LLM to identify the primary root cause of a grid issue.

    Prioritises unstable incident records when building context. Falls back to a
    static message if the LLM is unavailable. Emits a failure_analysis_complete event
    on the event bus when complete.
    """
    query    = state.get("query", "")
    docs     = state.get("retrieved_docs", [])
    stab_out = state.get("agent_outputs", {}).get("stability", {})

    with node_span("failure_analysis"):
        parts = []
        if stab_out.get("analysis"):
            parts.append(f"Stability analysis:\n{stab_out['analysis']}")
        if docs:
            unstable = [d for d in docs if d.get("metadata", {}).get("stabf") == "unstable"]
            # Prefer unstable-flagged records; fall back to all docs if none are flagged
            parts.append("Incident records:\n" + "\n".join(d["text"] for d in (unstable or docs)[:4]))
        context = truncate_context("\n\n".join(parts))

        root_cause = "LLM unavailable — manual inspection recommended."
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.core.llm_router import TaskType, router as llm_router
            msgs = [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=f"Grid issue: {query}\n\nContext:\n{context}"),
            ]
            resp       = llm_router.invoke(TaskType.ANALYSIS, msgs)
            root_cause = getattr(resp, "content", "") or root_cause
        except Exception as exc:
            logger.warning("failure_analysis_llm_failed", extra={"err": str(exc)})

        try:
            from app.services.event_bus import event_bus
            event_bus.emit("failure_analysis_complete", has_root_cause=bool(root_cause))
        except Exception:
            pass

    return {
        "agent_outputs": {
            **state.get("agent_outputs", {}),
            "failure_analysis": {"root_cause": root_cause},
        }
    }
