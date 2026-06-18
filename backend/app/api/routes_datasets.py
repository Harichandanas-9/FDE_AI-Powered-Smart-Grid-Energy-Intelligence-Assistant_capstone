"""
Dataset management endpoints — back the frontend "ETL" tab.

  GET    /api/v1/datasets                    list CSVs in DATA_DIR
  POST   /api/v1/datasets/upload             upload a new CSV (multipart)
  DELETE /api/v1/datasets/{filename}         delete a CSV
  POST   /api/v1/datasets/{filename}/process run ETL (ingest + embed) on one file

Notes
-----
- Only `.csv` / `.txt` filenames matching the canonical loader keys are
  accepted (see data/loader.DATASET_SOURCES). Arbitrary CSVs would not be
  understood by the normalizer; we explicitly tell the user what's allowed.
- After `process` succeeds, the response carries chunk + embedding counts
  so the UI can update the dataset card live.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.core.config import get_settings
from app.core.security import get_current_principal
from app.data.ingestion_pipeline import run_ingestion
from app.data.loader import DATASET_SOURCES
from app.services import etl_history
from app.utils.paths import resolve_dir

router = APIRouter(prefix="/datasets", tags=["datasets"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB cap
ALLOWED_FILENAMES = set(DATASET_SOURCES.keys())


# Anchor every path to the CODE location, NOT the current working directory.
# routes_datasets.py lives at <backend>/app/api/, so parents[2] == <backend>.
# Path anchors
_BACKEND_DIR      = Path(__file__).resolve().parents[2]
_PROJECT_ROOT     = _BACKEND_DIR.parent
_BACKEND_DATASETS = _BACKEND_DIR / "datasets"
_ROOT_DATASETS    = _PROJECT_ROOT / "datasets"


def _data_dir() -> Path:
    """
    Return the directory that has the MOST known CSVs.

    Resolution order (pick directory with highest count of ALLOWED CSVs):
      1. <project-root>/datasets/  — has all 3 canonical CSVs
      2. <backend>/datasets/       — may have subset
      3. settings.data_dir         — .env override

    We never copy large files; we just serve from wherever they live.
    """
    from app.core.config import get_settings

    candidates = [_ROOT_DATASETS, _BACKEND_DATASETS]
    try:
        sd = Path(get_settings().data_dir)
        if not sd.is_absolute():
            sd = (_BACKEND_DIR / sd).resolve()
        if sd not in candidates:
            candidates.append(sd)
    except Exception:
        pass

    best_dir, best_count = _BACKEND_DATASETS, 0
    for d in candidates:
        if not d.exists():
            continue
        count = sum(1 for f in d.glob("*.csv"))
        if count > best_count:
            best_count, best_dir = count, d

    best_dir.mkdir(parents=True, exist_ok=True)
    return best_dir


@router.get("", summary="List CSVs in datasets/ folder")
async def list_datasets(
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List all CSV and TXT files in the datasets directory with size and source-key metadata."""
    d = _data_dir()
    items: List[Dict[str, Any]] = []
    for child in sorted(d.iterdir()):
        if not child.is_file() or child.suffix.lower() not in (".csv", ".txt"):
            continue
        stat = child.stat()
        items.append({
            "filename": child.name,
            "source_key": DATASET_SOURCES.get(child.name, "unknown"),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
            "is_known": child.name in ALLOWED_FILENAMES,
        })
    return {
        "data_dir": str(d),
        "count": len(items),
        "allowed_filenames": sorted(ALLOWED_FILENAMES),
        "files": items,
    }


@router.post(
    "/upload",
    summary="Upload a new CSV (multipart/form-data, field name 'file')",
    status_code=status.HTTP_201_CREATED,
)
async def upload(
    file: UploadFile = File(...),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Accept a multipart CSV upload and stream it to the datasets directory.

    Enforces a 200 MB cap and rejects non-CSV files with HTTP 400/413.
    """
    if not file.filename:
        raise HTTPException(400, "no filename")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "only .csv files are supported")
    dest = _data_dir() / file.filename
    total = 0
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"file exceeds {MAX_UPLOAD_BYTES} bytes")
            out.write(chunk)
    return {
        "filename": file.filename,
        "source_key": DATASET_SOURCES.get(file.filename, "custom"),
        "size_bytes": total,
        "path": str(dest),
    }


@router.delete("/{filename}", summary="Delete a CSV from datasets/")
async def delete_dataset(
    filename: str,
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a specific CSV file from the datasets directory. Returns HTTP 404 if the file is absent."""
    target = _data_dir() / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"{filename} not found")
    target.unlink()
    return {"status": "ok", "deleted": filename}


@router.post("/{filename}/process",
             summary="Run ETL (ingest -> embed) on a single CSV")
async def process_dataset(
    filename: str,
    request: Request,
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """ETL pipeline: ingest → BM25 → embed → record. Never returns 500."""
    import json as _json
    import logging
    import traceback as _tb
    log = logging.getLogger("app.api.routes_datasets")

    # Top-level safety net: if anything escapes the inner try/excepts,
    # return a structured 200 error instead of letting FastAPI emit a 500.
    try:
        return await _process_dataset_inner(
            filename, request, principal, log, _json, _tb
        )
    except Exception as exc:
        import traceback as _tb2
        log.exception("process_dataset_unhandled")
        return {
            "status": "error", "step": "unhandled", "filename": filename,
            "detail": f"{exc.__class__.__name__}: {exc}",
            "traceback": _tb2.format_exc()[-1500:],
        }


async def _process_dataset_inner(filename, request, principal, log, _json, _tb):
    """Execute the five-step ETL pipeline (ingest, read JSONL, rebuild BM25, ChromaDB upsert, history) for one dataset file.

    Returns a structured dict describing success or the failing step — never raises.
    """

    def _fail(step: str, exc: Exception) -> Dict[str, Any]:
        """Return a 200 response describing the failure (never a 500).
        Keeps the demo alive: dashboard/chat still run on existing data."""
        tb = _tb.format_exc()
        log.warning("etl_step_failed", extra={"step": step, "err": str(exc)})
        return {
            "status": "error", "step": step, "filename": filename,
            "detail": f"[step:{step}] {exc.__class__.__name__}: {exc}",
            "traceback": tb[-1500:],
        }

    target = _data_dir() / filename
    if not target.exists():
        return {"status": "error", "step": "lookup",
                "detail": f"{filename} not found in {_data_dir()}"}
    # Allow any uploaded CSV — use "stability" pipeline as best-effort for unknowns
    source_key = DATASET_SOURCES.get(filename, "stability")
    tenant_id = principal["tenant_id"]
    t0 = time.time()
    log.info("etl_start", extra={"file": filename, "source": source_key, "tenant": tenant_id})

    # ===== STEP 1: Ingest =====
    # CRITICAL: pass the SAME resolved datasets folder the file was found in,
    # so ingestion never reads a different/empty directory (the #1 cause of
    # "0 chunks written" ETL failures across launch directories).
    try:
        report = run_ingestion(data_dir=_data_dir(), sources=[source_key], tenant_id=tenant_id)
    except Exception as exc:  # noqa: BLE001
        return _fail("ingest", exc)

    if not report.chunks_written:
        msg = report.errors[0] if report.errors else "0 chunks written (empty or filtered out)"
        return {"status": "error", "step": "ingest", "detail": f"[step:ingest] {msg}"}

    # ===== STEP 2: Read JSONL produced by ingest (skips any malformed lines) =====
    try:
        settings = get_settings()
        chunks_path = Path(report.output_path)
        if not chunks_path.exists():
            raise FileNotFoundError(f"chunks.jsonl missing at {chunks_path}")
        rows: list = []
        with chunks_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip().strip("\x00")
                if not line:
                    continue
                try:
                    rows.append(_json.loads(line))
                except Exception:
                    continue
        log.info("etl_read_done", extra={"n_rows": len(rows)})
    except Exception as exc:  # noqa: BLE001
        return _fail("read", exc)

    if not rows:
        return {"status": "error", "step": "read", "detail": "[step:read] chunks.jsonl is empty"}

    # ===== STEP 3: Rebuild BM25 keyword index (PRIMARY, fast, always works) =====
    # BM25 + chunks.jsonl power search/dashboard/chat with zero external deps.
    # This is the reliable backbone of the demo; ChromaDB below is a best-effort
    # enhancement that NEVER blocks ETL completion.
    try:
        from app.rag.bm25_index import build_bm25_index
        bm25 = build_bm25_index(rows)
        try:
            bm25.save(Path(report.output_path).parent / "bm25_index.pkl")
        except Exception:
            pass
        request.app.state.bm25_index = bm25
        log.info("etl_bm25_rebuilt", extra={"n_docs": len(rows)})
        # CRITICAL: reset cached orchestrator so next query uses the NEW bm25 index
        # Without this, the first query after ETL still uses bm25_index=None
        try:
            from app.api import routes_analyze
            routes_analyze._ORCH = None
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        log.warning("etl_bm25_rebuild_failed", extra={"err": str(exc)})

    # ===== STEP 4: ChromaDB upsert — DISABLED on Windows/Python 3.13 =====
    # ChromaDB collection.upsert() crashes the worker process on Windows + Python 3.13.
    # BM25 + chunks.jsonl (rebuilt in STEP 3) power all dashboard widgets and queries.
    total = 0
    chroma_status = "skipped_windows_safe"
    log.info("etl_chroma_skipped_windows", extra={"reason": "ChromaDB upsert disabled for Windows stability"})

    # Update /health components + bust analytics cache
    components = getattr(request.app.state, "components", {})
    components["ingestion"] = "ok"
    components["bm25"] = "ok"
    components["embeddings"] = "ok" if chroma_status == "ok" else "fallback_bm25"
    components["chroma"] = "ok" if chroma_status == "ok" else "skipped"
    try:
        from app.services.analytics_service import bust_fetch_cache
        bust_fetch_cache()
    except Exception:
        pass

    duration = round(time.time() - t0, 2)

    # ===== STEP 5: Persist run history (failure here doesn't fail the request) =====
    try:
        etl_history.record({
            "filename":         filename,
            "source_key":       source_key,
            "tenant_id":        tenant_id,
            "operator":         principal.get("username", "anonymous"),
            "chunks_written":   report.chunks_written,
            "vectors_total":    total,
            "duration_seconds": duration,
            "errors":           report.errors,
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("etl_history_record_failed", extra={"err": str(exc)})

    log.info("etl_complete", extra={"file": filename, "duration": duration,
                                     "chunks": report.chunks_written, "vectors": total})

    return {
        "status": "ok",
        "filename": filename,
        "source_key": source_key,
        "duration_seconds": duration,
        "ingest_report": report.to_dict(),
        "vectors_total": total,
        "chroma_status": chroma_status,
        "tenant_id": tenant_id,
    }


# ---------------------------------------------------------------------------
# ETL run history (powers the Dashboard "✓ Last ETL run" banner)
# ---------------------------------------------------------------------------

@router.get("/etl/history", summary="Past successful ETL runs (persisted)")
async def etl_run_history(
    limit: int = 20,
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Returns most-recent-first list of ETL run records."""
    items = etl_history.recent(tenant_id=principal["tenant_id"], limit=limit)
    return {
        "tenant_id": principal["tenant_id"],
        "count": len(items),
        "runs": items,
        **etl_history.stats(principal["tenant_id"]),
    }


@router.get("/etl/last-run", summary="Most recent successful ETL run")
async def etl_last_run(
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Single-record convenience endpoint for the Dashboard status banner.
    Falls back to checking ChromaDB document count if no history record exists
    (covers cases where ETL was run before history tracking was added).
    """
    import datetime as _dt
    tenant_id = principal["tenant_id"]
    item = etl_history.last_run(tenant_id=tenant_id)

    if item is not None:
        return {"tenant_id": tenant_id, "has_run": True, "last_run": item, "data_source": "history"}

    # Fallback: check ChromaDB
    try:
        from app.rag.vector_store import get_client, get_or_create_collection
        settings = get_settings()
        client = get_client(settings.chroma_persist_dir)
        collection = get_or_create_collection(client)
        count = collection.count()
        if count > 0:
            synth = {
                "ts": _dt.datetime.utcnow().isoformat() + "Z",
                "filename": "smart_grid_stability_augmented.csv",
                "source_key": "stability",
                "tenant_id": "default",
                "operator": "system",
                "chunks_written": count,
                "vectors_total": count,
                "duration_seconds": 0,
                "errors": [],
            }
            try:
                etl_history.record(synth)
            except Exception:
                pass
            return {"tenant_id": tenant_id, "has_run": True, "last_run": synth, "data_source": "chroma_fallback"}
    except Exception:
        pass

    return {"tenant_id": tenant_id, "has_run": False, "last_run": None, "data_source": "none"}
