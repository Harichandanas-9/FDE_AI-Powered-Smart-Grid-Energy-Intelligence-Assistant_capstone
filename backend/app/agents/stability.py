"""Grid Stability Agent — LangGraph node for telemetry stability analysis."""
from __future__ import annotations

from app.agents._common import node_span, truncate_context
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are the Grid Stability Agent. Analyze grid stability telemetry from retrieved incidents. "
    "Focus on: stability margins (stab), node reaction times (tau1-tau4), power injections (p1-p4), "
    "and price elasticity (g1-g4). Identify stability risks and threshold violations."
)


def analyze_stability(state: dict) -> dict:
    query = state.get("query", "")
    docs  = state.get("retrieved_docs", [])

    with node_span("stability_agent"):
        stable   = sum(1 for d in docs if d.get("metadata", {}).get("stabf") == "stable")
        unstable = sum(1 for d in docs if d.get("metadata", {}).get("stabf") == "unstable")
        stats    = (f"{stable} stable, {unstable} unstable. "
                    f"Instability rate: {unstable / max(len(docs), 1) * 100:.1f}%")
        ctx = truncate_context("\n".join(d["text"] for d in docs[:6]), max_chars=8000)

        analysis = stats  # fallback
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.core.llm_router import TaskType, router as llm_router
            msgs = [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=f"Query: {query}\n\nStats: {stats}\n\nTelemetry:\n{ctx}"),
            ]
            resp     = llm_router.invoke(TaskType.ANALYSIS, msgs)
            analysis = getattr(resp, "content", "") or stats
        except Exception as exc:
            logger.warning("stability_llm_failed", extra={"err": str(exc)})

        try:
            from app.services.event_bus import event_bus
            event_bus.emit("stability_analysis", stable_count=stable, unstable_count=unstable)
        except Exception:
            pass

    return {
        "agent_outputs": {
            **state.get("agent_outputs", {}),
            "stability": {"analysis": analysis, "stable_count": stable, "unstable_count": unstable},
        }
    }
