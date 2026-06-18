"""
Dashboard analytics endpoints.

  GET /api/v1/grid-score        Overall + per-region grid health score
  GET /api/v1/heatmap            Region x severity matrix
  GET /api/v1/timeline?bucket=   Chronological incident series
  GET /api/v1/telemetry          Recent telemetry samples
  GET /api/v1/recommendations    Cached recent /analyze responses

All endpoints are tenant-aware: chunks tagged with the caller's tenant_id
and the shared "default" tenant are included.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_principal
from app.services import analytics_service as svc

router = APIRouter(tags=["analytics"])


@router.get("/grid-score", summary="Overall + per-region grid health score")
async def grid_score(principal: dict = Depends(get_current_principal)) -> Dict[str, Any]:
    """Return the overall grid health score and a breakdown by region for the caller's tenant."""
    return {"tenant_id": principal["tenant_id"],
            **svc.grid_health_score(principal["tenant_id"])}


@router.get("/heatmap", summary="Region x severity incident heatmap")
async def heatmap(principal: dict = Depends(get_current_principal)) -> Dict[str, Any]:
    """Return a region-by-severity incident count matrix for the heatmap dashboard widget."""
    return {"tenant_id": principal["tenant_id"],
            **svc.heatmap_data(principal["tenant_id"])}


@router.get("/timeline", summary="Chronological incidents")
async def timeline(
    bucket: str = Query(default="day", pattern="^(day|hour)$"),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Return chronological incident counts bucketed by day or hour for timeline charts."""
    return {"tenant_id": principal["tenant_id"],
            **svc.timeline_data(principal["tenant_id"], bucket=bucket)}


@router.get("/telemetry", summary="Recent telemetry summary")
async def telemetry(
    limit: int = Query(default=100, ge=1, le=1000),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Return a summary of the most recent telemetry samples (voltage, frequency, stability)."""
    return {"tenant_id": principal["tenant_id"],
            **svc.telemetry_summary(principal["tenant_id"], limit=limit)}


@router.get("/recommendations", summary="Recent recommendation cache")
async def recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Return the most recent cached /analyze recommendations for the tenant."""
    items = svc.recent_recommendations(principal["tenant_id"], limit=limit)
    return {"tenant_id": principal["tenant_id"], "count": len(items),
            "recommendations": items}


@router.get("/qa-history", summary="Past questions (FAQ) — persisted across restarts")
async def qa_history(
    limit: int = Query(default=20, ge=1, le=100),
    unique: bool = Query(default=True, description="De-duplicate similar questions"),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Return past user questions along with frequency stats, optionally de-duplicated."""
    items = svc.question_history(principal["tenant_id"], limit=limit, unique=unique)
    stats = svc.history_stats(principal["tenant_id"])
    return {
        "tenant_id":    principal["tenant_id"],
        "count":        len(items),
        "questions":    items,
        **stats,
    }


@router.get("/forecast", summary="Demand forecasting — rolling avg + 3-day projection")
async def demand_forecast(principal: dict = Depends(get_current_principal)) -> Dict[str, Any]:
    """Return a rolling-average demand history and a 3-day forward projection."""
    return {"tenant_id": principal["tenant_id"],
            **svc.demand_forecast(principal["tenant_id"])}


@router.get("/correlations", summary="Anomaly correlation matrix between telemetry signals")
async def anomaly_correlations(principal: dict = Depends(get_current_principal)) -> Dict[str, Any]:
    """Return pairwise correlation coefficients between key telemetry signals for anomaly analysis."""
    return {"tenant_id": principal["tenant_id"],
            **svc.anomaly_correlations(principal["tenant_id"])}
