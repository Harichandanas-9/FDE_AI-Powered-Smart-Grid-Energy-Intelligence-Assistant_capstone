"""Recommendation + Synthesis Agents — LangGraph nodes."""
from __future__ import annotations

from app.agents._common import node_span, truncate_context
from app.core.logging import get_logger

logger = get_logger(__name__)

_REC_SYSTEM = (
    "You are the Grid Recommendation Agent. Generate clear, actionable mitigation recommendations. "
    "Structure: **Immediate Actions** (0-30 min), **Short-term** (1-24 hrs), **Long-term** (weeks/months). "
    "Ground recommendations in telemetry evidence."
)
_SYNTH_SYSTEM = (
    "You are a smart-grid intelligence assistant. Combine the provided agent analyses into a clear, "
    "comprehensive response for a grid operator. Use markdown formatting."
)


def recommend(state: dict) -> dict:
    query         = state.get("query", "")
    severity      = state.get("severity", "LOW")
    agent_outputs = state.get("agent_outputs", {})

    with node_span("recommendation"):
        parts = [f"Grid issue: {query}", f"Severity: {severity}"]
        if agent_outputs.get("grid_retrieval", {}).get("summary"):
            parts.append(f"Incidents:\n{agent_outputs['grid_retrieval']['summary']}")
        if agent_outputs.get("stability", {}).get("analysis"):
            parts.append(f"Stability:\n{agent_outputs['stability']['analysis']}")
        if agent_outputs.get("failure_analysis", {}).get("root_cause"):
            parts.append(f"Root cause:\n{agent_outputs['failure_analysis']['root_cause']}")

        context         = truncate_context("\n\n".join(parts))
        recommendations = "LLM unavailable — review stability and failure analyses."
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.core.llm_router import TaskType, router as llm_router
            resp            = llm_router.invoke(TaskType.GENERATION,
                                                [SystemMessage(content=_REC_SYSTEM),
                                                 HumanMessage(content=context)])
            recommendations = getattr(resp, "content", "") or recommendations
        except Exception as exc:
            logger.warning("recommendation_llm_failed", extra={"err": str(exc)})

        try:
            from app.services.event_bus import event_bus
            event_bus.emit("recommendations_generated", severity=severity)
        except Exception:
            pass

    return {
        "agent_outputs": {
            **agent_outputs,
            "recommendation": {"recommendations": recommendations, "severity": severity},
        }
    }


def synthesize_final(state: dict) -> dict:
    query         = state.get("query", "")
    agent_outputs = state.get("agent_outputs", {})

    parts = []
    if agent_outputs.get("grid_retrieval", {}).get("summary"):
        parts.append(f"**Retrieved Incidents:**\n{agent_outputs['grid_retrieval']['summary']}")
    if agent_outputs.get("stability", {}).get("analysis"):
        parts.append(f"**Stability Analysis:**\n{agent_outputs['stability']['analysis']}")
    if agent_outputs.get("failure_analysis", {}).get("root_cause"):
        parts.append(f"**Root Cause Analysis:**\n{agent_outputs['failure_analysis']['root_cause']}")
    if agent_outputs.get("recommendation", {}).get("recommendations"):
        parts.append(f"**Mitigation Recommendations:**\n{agent_outputs['recommendation']['recommendations']}")

    if not parts:
        return {"final_answer": "Unable to generate analysis. Please check that data has been ingested."}

    context = truncate_context("\n\n".join(parts))
    final   = "\n\n".join(parts)  # fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.core.llm_router import TaskType, router as llm_router
        resp  = llm_router.invoke(TaskType.GENERATION,
                                  [SystemMessage(content=_SYNTH_SYSTEM),
                                   HumanMessage(content=f"Grid query: {query}\n\n{context}")])
        final = getattr(resp, "content", "") or final
    except Exception as exc:
        logger.warning("synthesize_llm_failed", extra={"err": str(exc)})

    return {"final_answer": final}
