"""
Persistent ETL run log.

Every successful /datasets/{name}/process call appends one line to
data_processed/etl_history.jsonl, so the Dashboard can show a real
"✓ Last ETL run: <timestamp>" badge across page reloads and restarts.

Each record:
{
    "ts": "2026-06-03T10:15:42Z",
    "filename": "smart_grid_stability_augmented.csv",
    "source_key": "stability",
    "tenant_id": "default",
    "operator": "Hani",
    "chunks_written": 60000,
    "vectors_total": 60000,
    "duration_seconds": 45.2,
    "errors": []
}
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.utils.paths import resolve_dir

logger = get_logger(__name__)

_LOCK = Lock()
_CACHE: List[Dict[str, Any]] = []
_CACHE_LIMIT = 200


def _history_path() -> Path:
    return resolve_dir("./data_processed", create=True) / "etl_history.jsonl"


def load_history() -> int:
    """Load on app startup. Returns row count."""
    global _CACHE
    p = _history_path()
    if not p.exists():
        return 0
    rows: List[Dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("etl_history_load_failed", extra={"err": str(exc)})
        return 0

    with _LOCK:
        _CACHE = list(reversed(rows[-_CACHE_LIMIT:]))   # newest first
    logger.info("etl_history_loaded", extra={"count": len(_CACHE)})
    return len(_CACHE)


def record(item: Dict[str, Any]) -> None:
    """Append a new ETL run to disk + cache."""
    if "ts" not in item:
        item["ts"] = datetime.utcnow().isoformat() + "Z"
    p = _history_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001 — never break the request
        logger.warning("etl_history_persist_failed", extra={"err": str(exc)})
    with _LOCK:
        _CACHE.insert(0, item)
        del _CACHE[_CACHE_LIMIT:]


def recent(tenant_id: str = "default", limit: int = 20) -> List[Dict[str, Any]]:
    """Most-recent-first list of past ETL runs visible to this tenant."""
    out: List[Dict[str, Any]] = []
    for r in _CACHE:
        if r.get("tenant_id", "default") != tenant_id and tenant_id != "default":
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def last_run(tenant_id: str = "default") -> Optional[Dict[str, Any]]:
    items = recent(tenant_id=tenant_id, limit=1)
    return items[0] if items else None


def stats(tenant_id: str = "default") -> Dict[str, Any]:
    runs = recent(tenant_id=tenant_id, limit=_CACHE_LIMIT)
    return {
        "total_runs":       len(runs),
        "total_chunks":     sum(r.get("chunks_written", 0) for r in runs),
        "total_vectors":    runs[0].get("vectors_total", 0) if runs else 0,
        "files_processed":  sorted({r.get("filename") for r in runs if r.get("filename")}),
        "last_run":         runs[0] if runs else None,
        "history_file":     str(_history_path()),
    }
