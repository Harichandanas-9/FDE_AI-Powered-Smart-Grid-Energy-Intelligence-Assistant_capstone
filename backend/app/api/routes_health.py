"""
GET /health — liveness + component status.

Status logic
------------
A status value belongs to one of three buckets:

  HEALTHY  — everything that's working OR is in a normal lazy/cold state
             (e.g. "fallback_template" for LLM means we're using the offline
             provider, which is *fine*; "empty" for qa_history means no
             questions yet, *fine*; "not_run" for ingestion means user hasn't
             clicked ETL yet, *fine*).

  WARN     — something is missing but recoverable by the operator
             (e.g. "no_chunks" means BM25 has nothing to index until ETL runs).

  ERROR    — something is broken / a dependency is missing
             (e.g. "not_installed", "error").

The endpoint reports:
  status = "ok"        if no component is in ERROR
  status = "degraded"  otherwise
"""
from typing import Dict

from fastapi import APIRouter, Request

from app import __version__

router = APIRouter(tags=["health"])

HEALTHY = {
    "ok",
    "not_initialized",      # lazy resource, fine
    "not_run",              # ingestion hasn't been triggered yet
    "fallback_template",    # LLM using deterministic offline provider — by design
    "configured",           # LLM provider has an API key
    "disabled",             # auth disabled (single-tenant mode default)
    "enabled",              # auth enabled (multi-tenant mode)
    "empty",                # qa_history with no questions yet
}
ERROR = {"error", "not_installed"}


def _classify(value: str) -> str:
    """Map a component status string to one of 'healthy', 'warn', or 'error'."""
    if isinstance(value, str) and value.startswith("ok"):  # e.g. "ok (5 loaded)"
        return "healthy"
    if value in HEALTHY:
        return "healthy"
    if value in ERROR:
        return "error"
    return "warn"  # e.g. "no_chunks"


@router.get("/health", summary="Liveness + component status")
async def health(request: Request) -> Dict:
    """Return liveness status and per-component health, aggregated to 'ok', 'warn', or 'degraded'."""
    components: Dict[str, str] = getattr(request.app.state, "components", {})
    has_error = any(_classify(v) == "error" for v in components.values())
    has_warn  = any(_classify(v) == "warn"  for v in components.values())
    status = "degraded" if has_error else ("warn" if has_warn else "ok")
    return {
        "status": status,
        "version": __version__,
        "components": components,
    }


@router.get("/", summary="Root banner")
async def root() -> Dict:
    """Return a brief service banner with links to docs and the health endpoint."""
    return {
        "service": "Smart Grid AI Assistant",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
