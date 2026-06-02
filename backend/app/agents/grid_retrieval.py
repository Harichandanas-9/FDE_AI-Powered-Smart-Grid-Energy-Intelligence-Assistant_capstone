"""Grid Retrieval Agent — LangGraph node wrapping the hybrid retriever."""
from __future__ import annotations

from app.agents._common import node_span, truncate_context
from app.core.logging import get_logger

logger = get_logger(__name__)


def retrieve(state: dict) -> dict:
    query    = state.get("query", "")
    severity = state.get("severity", "LOW")
    where    = {"severity": "HIGH"} if severity == "HIGH" else None

    with node_span("grid_retrieval"):
        from app.rag.hybrid_retriever import HybridRetriever
        from app.core.config import get_settings
        chunks = HybridRetriever(get_settings()).retrieve(query, where=where)

        docs = [
            {"id": c.id, "text": c.text, "metadata": c.metadata,
             "score": c.score, "semantic_rank": c.semantic_rank,
             "keyword_rank": c.keyword_rank}
            for c in chunks
        ]

        summary = ""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.core.llm_router import TaskType, router as llm_router
            context = truncate_context("\n\n".join(d["text"] for d in docs[:5]))
            msgs = [
                SystemMessage(content=(
                    "You are the Grid Retrieval Agent. Given a grid query and retrieved "
                    "incident documents, identify the most relevant incidents. Be concise."
                )),
                HumanMessage(content=f"Query: {query}\n\nRetrieved incidents:\n{context}"),
            ]
            resp    = llm_router.invoke(TaskType.ANALYSIS, msgs)
            summary = getattr(resp, "content", "") or ""
        except Exception as exc:
            logger.warning("grid_retrieval_summary_failed", extra={"err": str(exc)})

        try:
            from app.services.event_bus import event_bus
            event_bus.emit("retrieval_complete", docs_count=len(docs))
        except Exception:
            pass

    return {
        "retrieved_docs": docs,
        "agent_outputs": {
            **state.get("agent_outputs", {}),
            "grid_retrieval": {"summary": summary, "doc_count": len(docs)},
        },
    }
