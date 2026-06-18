"""LangGraph multi-agent pipeline for smart grid intelligence.

Uses MemorySaver for session checkpointing — NOT SqliteSaver.
The SqliteSaver context manager API broke in LangGraph 0.2.50+; MemorySaver
is the correct replacement for single-process deployments.

Graph topology:
    orchestrator → grid_retrieval → stability → failure_analysis
                                                      ↓
                                              recommendation → synthesize → END
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── State ──────────────────────────────────────────────────────────────────
class GridState(TypedDict):
    """Shared state dict passed between every node in the LangGraph pipeline."""

    query: str
    session_id: str
    messages: List[BaseMessage]
    intent: str
    severity: str
    retrieved_docs: List[Dict[str, Any]]
    agent_outputs: Dict[str, Any]
    final_answer: str
    reformulated_from: Optional[str]
    needs_human: bool


# ── Routing ────────────────────────────────────────────────────────────────
def _route_after_orchestrator(state: GridState) -> str:
    """Route all recognized intents to grid_retrieval as the first data-fetching step."""
    intent = state.get("intent", "general")
    return {
        "grid_retrieval":    "grid_retrieval",
        "stability_analysis": "grid_retrieval",
        "failure_analysis":  "grid_retrieval",
        "recommendation":    "grid_retrieval",
    }.get(intent, "grid_retrieval")


def _route_after_retrieval(state: GridState) -> str:
    """Skip stability and go directly to failure_analysis when the intent is a failure investigation."""
    if state.get("intent") == "failure_analysis":
        return "failure_analysis"
    return "stability"


# ── Node wrappers ──────────────────────────────────────────────────────────
def _orchestrate(state: GridState) -> dict:
    """Classify the incoming query into an intent and severity via the LLM router.

    Parses the LLM's JSON response and falls back to intent="general", severity="LOW"
    if the call fails or the response is malformed.
    """
    import json
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_router import TaskType, router as llm_router

    SYSTEM = (
        "Classify this smart-grid query into ONE intent and severity. "
        "Intents: grid_retrieval, stability_analysis, failure_analysis, recommendation, general. "
        "Severity: LOW, MEDIUM, HIGH. "
        'Return strict JSON: {"intent": "...", "severity": "...", "rationale": "..."}'
    )
    try:
        msgs = [SystemMessage(content=SYSTEM), HumanMessage(content=state.get("query", ""))]
        resp = llm_router.invoke(TaskType.ROUTING, msgs)
        raw = getattr(resp, "content", "") or ""
        i, j = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[i:j + 1]) if 0 <= i < j else {}
    except Exception:
        parsed = {}

    intent   = parsed.get("intent", "general")
    severity = parsed.get("severity", "LOW").upper()
    if severity not in ("LOW", "MEDIUM", "HIGH"):
        severity = "LOW"
    logger.info(f"[graph/orchestrator] intent={intent} severity={severity}")
    return {"intent": intent, "severity": severity, "agent_outputs": {"orchestrator": parsed}}


def _retrieve(state: GridState) -> dict:
    """LangGraph node: delegate to the grid_retrieval module's retrieve function."""
    from app.agents.grid_retrieval import retrieve
    return retrieve(state)


def _stability(state: GridState) -> dict:
    """LangGraph node: delegate to the stability module's analyze_stability function."""
    from app.agents.stability import analyze_stability
    return analyze_stability(state)


def _failure(state: GridState) -> dict:
    """LangGraph node: delegate to the failure_analysis module's analyze_failure function."""
    from app.agents.failure_analysis import analyze_failure
    return analyze_failure(state)


def _recommend(state: GridState) -> dict:
    """LangGraph node: delegate to the recommendation module's recommend function."""
    from app.agents.recommendation import recommend
    return recommend(state)


def _synthesize(state: GridState) -> dict:
    """LangGraph node: delegate to the recommendation module's synthesize_final function."""
    from app.agents.recommendation import synthesize_final
    return synthesize_final(state)


# ── Graph build ────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_graph():
    """Compile the LangGraph agent graph. Result is cached — call freely."""
    memory = MemorySaver()

    builder = StateGraph(GridState)
    builder.add_node("orchestrator",     _orchestrate)
    builder.add_node("grid_retrieval",   _retrieve)
    builder.add_node("stability",        _stability)
    builder.add_node("failure_analysis", _failure)
    builder.add_node("recommendation",   _recommend)
    builder.add_node("synthesize",       _synthesize)

    builder.set_entry_point("orchestrator")
    builder.add_conditional_edges("orchestrator",   _route_after_orchestrator)
    builder.add_conditional_edges("grid_retrieval", _route_after_retrieval)
    builder.add_edge("stability",        "failure_analysis")
    builder.add_edge("failure_analysis", "recommendation")
    builder.add_edge("recommendation",   "synthesize")
    builder.add_edge("synthesize",       END)

    graph = builder.compile(checkpointer=memory)
    logger.info("[graph] Smart grid LangGraph pipeline compiled with MemorySaver")
    return graph
