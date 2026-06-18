"""
POST /api/v1/analyze — the headline endpoint, powered by the multi-agent
orchestrator (STEP 7). Every response carries an `agent_trace` so the
frontend can render the agent-flow visualization.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Request

from app.agents.orchestrator import AgentOrchestrator
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_principal
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import analytics_service

logger = get_logger(__name__)

router = APIRouter(tags=["analyze"])

_ORCH: Optional[AgentOrchestrator] = None


def _get_orchestrator(request: Request) -> AgentOrchestrator:
    """Return the module-level AgentOrchestrator singleton, creating it on first call.

    The BM25 index is sourced from app state so the orchestrator always uses
    the most recently ingested keyword index.
    """
    global _ORCH
    if _ORCH is None:
        bm25 = getattr(request.app.state, "bm25_index", None)
        _ORCH = AgentOrchestrator(settings=get_settings(), bm25_index=bm25)
    return _ORCH


@router.post("/analyze", summary="Natural-language grid incident analysis (multi-agent)")
async def analyze(
    req: AnalyzeRequest,
    request: Request,
    principal: dict = Depends(get_current_principal),
    x_operator_name: Optional[str] = Header(default=None, alias="X-Operator-Name"),
):
    """Run a natural-language grid incident analysis through the multi-agent orchestrator.

    Applies optional region/severity/source filters, offloads the synchronous
    orchestrator to a thread executor, caches the result for the recommendations
    widget, and returns a filtered response dict to avoid FastAPI validation errors
    on unexpected envelope keys.
    """
    orch = _get_orchestrator(request)
    filters: Dict[str, Any] = {}
    if req.region:   filters["region"] = req.region
    if req.severity: filters["severity"] = req.severity
    if req.source:   filters["source_dataset"] = req.source

    operator = x_operator_name or principal["username"]
    tenant_id = principal["tenant_id"]
    logger.info("analyze_query",
                extra={"operator": operator, "tenant_id": tenant_id,
                       "query": req.query[:200]})

    # Run synchronous orchestrator in thread executor — critical for Python 3.13
    # where blocking the async event loop causes worker crashes on Windows.
    import asyncio, functools
    try:
        _run = functools.partial(
            orch.run, req.query,
            tenant_id=tenant_id, filters=filters or None, top_k=req.top_k
        )
        loop = asyncio.get_event_loop()
        envelope = await loop.run_in_executor(None, _run)
    except Exception as exc:
        logger.exception("orchestrator_run_failed")
        # Return a graceful 200 with error status instead of 500
        return AnalyzeResponse(
            status="error",
            guardrail={"allow": True, "reasons": [], "pii_masked": {}, "pii_blocked": {}},
            query=req.query,
            answer=f"Analysis failed: {exc.__class__.__name__}: {exc}. Please try again.",
            tenant_id=tenant_id,
            operator=operator,
        )

    # Cache for /recommendations widget
    if envelope.get("status") == "ok":
        try:
            analytics_service.record_recommendation({
                "tenant_id": tenant_id,
                "operator": operator,
                "query": req.query,
                "answer": envelope.get("answer"),
                "recommendations": envelope.get("recommendations", []),
                "confidence": envelope.get("confidence", 0),
                "ts": envelope.get("duration_seconds", 0),
            })
        except Exception:
            pass

    envelope["operator"] = operator
    # Return as plain dict — avoids ResponseValidationError on unknown fields
    # (escalation_health_score and other extra keys cause FastAPI 500 with response_model)
    safe_keys = {
        "status","guardrail","query","masked_query","answer","root_causes",
        "recommendations","confidence","reasoning","retrieved","stability_analysis",
        "agent_trace","provider","duration_seconds","operator","tenant_id",
        "escalation_required","escalation_level","escalation_reason","escalation_regions",
    }
    return {k: v for k, v in envelope.items() if k in safe_keys}
