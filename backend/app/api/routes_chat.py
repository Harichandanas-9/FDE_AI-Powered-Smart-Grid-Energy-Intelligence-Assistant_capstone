"""
POST /api/v1/chat/query        — LangGraph chat with semantic cache.
POST /api/v1/chat/feedback     — thumbs-up/down ratings.
GET  /api/v1/chat/feedback/recent — last 50 ratings.
WS   /api/v1/chat/ws/{session_id} — streaming chat over WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.websockets import WebSocket, WebSocketDisconnect

from app.cache.semantic_cache import semantic_cache
from app.core.logging import get_logger
from app.models.schemas import ChatRequest, ChatResponse, FeedbackRequest, RetrievedChunkOut
from app.services.feedback_store import feedback_store

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _run_graph(query: str, session_id: str) -> Dict[str, Any]:
    """Build the LangGraph agent graph, invoke it synchronously, and return the final state dict.

    Intended to run inside a thread executor to avoid blocking the async event loop.
    """
    from langchain_core.messages import HumanMessage
    from app.agents.graph import get_graph
    from app.services.event_bus import set_session_id
    set_session_id(session_id)
    graph  = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    init   = {
        "query": query, "session_id": session_id,
        "messages": [HumanMessage(content=query)],
        "agent_outputs": {}, "retrieved_docs": [],
        "needs_human": False, "intent": "", "severity": "LOW",
        "final_answer": "", "reformulated_from": None,
    }
    return graph.invoke(init, config=config)


def _docs_out(docs, limit: int = 5):
    """Deduplicate and convert raw retrieved-doc dicts to RetrievedChunkOut models, up to `limit` items."""
    seen, out = set(), []
    for d in docs:
        did = d.get("id", "")
        if did in seen:
            continue
        seen.add(did)
        out.append(RetrievedChunkOut(
            id=did, text=d.get("text", ""),
            score=float(d.get("score", 0.0)),
            metadata=d.get("metadata", {}),
            semantic_rank=d.get("semantic_rank"),
            keyword_rank=d.get("keyword_rank"),
        ))
        if len(out) >= limit:
            break
    return out


@router.post("/query", response_model=ChatResponse, summary="LangGraph chat query")
async def chat_query(req: ChatRequest) -> ChatResponse:
    """Process a chat query through guardrails, a semantic cache lookup, then the LangGraph pipeline.

    Returns a cached response immediately if the query embedding is close enough to a prior query;
    otherwise runs the full multi-agent graph and caches the result.
    """
    try:
        from app.utils.guardrails import validate_query
        verdict = validate_query(req.query)
        if not verdict.allow:
            raise HTTPException(status_code=400, detail=verdict.response_message)
    except HTTPException:
        raise
    except Exception:
        pass

    session_id = req.session_id or str(uuid.uuid4())

    q_emb = None
    try:
        from app.rag.embeddings import embed_query
        from app.core.config import get_settings
        q_emb  = embed_query(req.query, model_name=get_settings().embedding_model).tolist()
        cached = semantic_cache.get(q_emb)
        if cached:
            return ChatResponse(**{**cached, "from_cache": True, "session_id": session_id})
    except Exception as exc:
        logger.debug("cache_lookup_skipped", extra={"err": str(exc)})

    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _run_graph, req.query, session_id
        )
    except Exception as exc:
        logger.exception("graph_execution_failed")
        raise HTTPException(status_code=500, detail=str(exc))

    answer    = state.get("final_answer") or "Analysis complete."
    resp_data = {
        "answer": answer, "session_id": session_id,
        "intent": state.get("intent"), "severity": state.get("severity"),
        "retrieved_docs": _docs_out(state.get("retrieved_docs", [])),
        "agent_outputs": state.get("agent_outputs", {}),
        "reformulated_from": state.get("reformulated_from"),
        "from_cache": False,
    }

    if q_emb:
        try:
            semantic_cache.put(q_emb, req.query, resp_data)
        except Exception:
            pass

    return ChatResponse(**resp_data)


@router.post("/feedback", summary="Store thumbs-up/down")
async def post_feedback(req: FeedbackRequest) -> dict:
    """Persist a thumbs-up or thumbs-down rating for a specific message."""
    feedback_store.save(req.session_id, req.message_id, req.rating, req.comment or "")
    return {"status": "ok"}


@router.get("/feedback/recent", summary="Recent feedback")
async def get_recent_feedback() -> dict:
    """Return the 50 most recent feedback entries along with aggregate stats."""
    return {"feedback": feedback_store.recent(), **feedback_store.stats()}


@router.websocket("/ws/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    """Stream chat responses over a WebSocket connection.

    Each received JSON message must contain a `query` key. After the graph
    completes, any buffered event-bus events for the session are also pushed.
    """
    await ws.accept()
    try:
        while True:
            data       = await ws.receive_text()
            payload    = json.loads(data)
            query_text = payload.get("query", "")
            if not query_text:
                continue
            try:
                from app.utils.guardrails import validate_query
                verdict = validate_query(query_text)
                if not verdict.allow:
                    await ws.send_text(json.dumps({"type": "error", "message": verdict.response_message}))
                    continue
            except Exception:
                pass

            await ws.send_text(json.dumps({"type": "status", "content": "Routing query..."}))
            try:
                state = await asyncio.get_event_loop().run_in_executor(
                    None, _run_graph, query_text, session_id
                )
                await ws.send_text(json.dumps({
                    "type": "answer", "content": state.get("final_answer", ""),
                    "intent": state.get("intent"), "severity": state.get("severity"),
                    "agent_outputs": state.get("agent_outputs", {}),
                }))
                try:
                    from app.services.event_bus import event_bus
                    for ev in event_bus.drain(session_id):
                        kind = ev.pop("type", "event")
                        await ws.send_text(json.dumps({"type": kind, **ev}))
                except Exception:
                    pass
            except Exception as exc:
                await ws.send_text(json.dumps({"type": "error", "message": str(exc)}))
    except WebSocketDisconnect:
        logger.info(f"[ws/chat] session {session_id} disconnected")
