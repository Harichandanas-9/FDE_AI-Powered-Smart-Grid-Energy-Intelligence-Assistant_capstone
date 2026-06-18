"""
POST /api/v1/ingest — run the data ingestion pipeline.

Behavior:
  - The pipeline can take 10–60s depending on max_rows. We run it inline
    (not as a background task) so the response carries the full report —
    this is the right shape for a demo and for STEP 4 which depends on the
    chunks.jsonl artifact being ready when the call returns.
  - A subsequent GET /api/v1/ingest/status returns the last report.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.data.ingestion_pipeline import IngestionReport, run_ingestion
from app.models.schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Module-level cache of the last report — small and OK for a single worker.
_last_report: Optional[IngestionReport] = None
_last_run_at: Optional[datetime] = None


@router.post("", response_model=IngestResponse, summary="Run data ingestion")
async def ingest(req: IngestRequest, request: Request) -> IngestResponse:
    """Run the data ingestion pipeline synchronously and return a full report.

    Updates the app component state so /health reflects whether chunks were written.
    """
    global _last_report, _last_run_at
    try:
        report = run_ingestion(
            sources=req.sources,
            max_rows_override=req.max_rows,
        )
    except Exception as exc:  # surface clearly in response
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _last_report = report
    _last_run_at = datetime.utcnow()

    # Toggle component status on the app so /health reflects readiness.
    components = getattr(request.app.state, "components", {})
    if report.chunks_written > 0:
        components["ingestion"] = "ok"
    else:
        components["ingestion"] = "no_chunks"

    return IngestResponse(
        status="ok" if report.chunks_written > 0 and not report.errors else "partial",
        duration_seconds=round(report.duration_seconds, 2),
        chunks_written=report.chunks_written,
        per_source=report.per_source,
        output_path=report.output_path,
        errors=report.errors,
    )


@router.get("/status", summary="Last ingestion report")
async def ingest_status() -> dict:
    """Return the report from the most recent ingestion run, or `never_run` if none has been triggered."""
    if _last_report is None:
        return {"status": "never_run"}
    return {
        "status": "ok",
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        **_last_report.to_dict(),
    }
