"""
Analytics service — aggregations over the Chroma `grid_incidents` collection
that power the dashboard widgets.

All functions take a `tenant_id` so the same backend serves multi-tenant
deployments correctly. They tolerate an empty collection and return shapes
the frontend can render without special-casing.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional  # noqa: F401

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.vector_store import get_client, get_or_create_collection

import time as _time

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory result cache for _fetch_all — prevents 6 parallel dashboard
# widgets each making a separate ChromaDB scan on every page load.
# TTL = 30 s; invalidated by bust_fetch_cache() after every ETL run.
# ---------------------------------------------------------------------------
_FETCH_CACHE: Dict[str, Any] = {}
_FETCH_CACHE_TTL: float = 30.0   # seconds


def bust_fetch_cache() -> None:
    """Call this after ETL completes so the next dashboard load gets fresh data."""
    _FETCH_CACHE.clear()
    logger.info("fetch_cache_busted")


def _fetch_all(tenant_id: str, max_rows: int = 2000) -> List[Dict[str, Any]]:
    """
    Return chunks visible to the given tenant.
    Results are cached in memory for 30 s so all dashboard widgets
    share a single ChromaDB round-trip per page load.
    """
    cache_key = f"{tenant_id}:{max_rows}"
    now = _time.monotonic()
    cached = _FETCH_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _FETCH_CACHE_TTL:
        return cached[1]

    # Use chunks.jsonl — ChromaDB collection.get() crashes Windows workers
    rows = _fetch_from_jsonl(max_rows)
    _FETCH_CACHE[cache_key] = (_time.monotonic(), rows)
    return rows
    return rows


def _fetch_from_jsonl(max_rows: int = 2000) -> List[Dict[str, Any]]:
    """Read directly from chunks.jsonl when ChromaDB is empty or unavailable."""
    import json as _json
    try:
        from app.utils.paths import resolve_dir
        chunks_path = resolve_dir("./data_processed", create=False) / "chunks.jsonl"
        if not chunks_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = _json.loads(line)
                    # Ensure format matches what analytics functions expect
                    if "id" in chunk and "text" in chunk:
                        rows.append({
                            "id": chunk["id"],
                            "text": chunk.get("text", ""),
                            "metadata": chunk.get("metadata", {}),
                        })
                    if len(rows) >= max_rows:
                        break
                except Exception:
                    continue
        return rows
    except Exception as exc:
        logger.warning("jsonl_fallback_failed", extra={"err": str(exc)})
        return []


# --------------------------------------------------------------------------- #
def grid_health_score(tenant_id: str) -> Dict[str, Any]:
    """Overall + per-region health score from currently stored incidents."""
    rows = _fetch_all(tenant_id)
    if not rows:
        return {"overall_score": None, "n_incidents": 0, "per_region": {}}

    NOM_V, NOM_F = 230.0, 50.0
    stabs, v_devs, f_devs, outages = [], [], [], 0
    per_region_acc: Dict[str, Dict[str, list]] = defaultdict(
        lambda: {"stab": [], "v": [], "f": []}
    )

    for r in rows:
        m = r["metadata"]
        s = float(m.get("stability_score_mean", 0) or 0)
        v = float(m.get("voltage_mean", NOM_V) or NOM_V)
        f = float(m.get("frequency_mean", NOM_F) or NOM_F)
        region = m.get("region", "Unknown")
        outages += int(m.get("outage_event", 0) or 0)

        stabs.append(s); v_devs.append(abs(v - NOM_V) / NOM_V); f_devs.append(abs(f - NOM_F))
        per_region_acc[region]["stab"].append(s)
        per_region_acc[region]["v"].append(abs(v - NOM_V) / NOM_V)
        per_region_acc[region]["f"].append(abs(f - NOM_F))

    def _score(stab_vals, v_vals, f_vals, n_out=0):
        avg_stab = sum(stab_vals) / len(stab_vals) if stab_vals else 0
        max_v = max(v_vals) if v_vals else 0
        max_f = max(f_vals) if f_vals else 0
        stab_t = max(0.0, min(1.0, (avg_stab + 1) / 2))
        v_t = max(0.0, 1 - max_v / 0.2)
        f_t = max(0.0, 1 - max_f / 2.0)
        out_penalty = min(0.3, 0.05 * n_out)
        return round(max(0.0, min(100.0,
                                  100 * (0.4 * stab_t + 0.3 * v_t + 0.3 * f_t)
                                  - out_penalty * 100)), 1)

    overall = _score(stabs, v_devs, f_devs, outages)
    per_region = {
        reg: _score(d["stab"], d["v"], d["f"])
        for reg, d in per_region_acc.items()
    }
    return {
        "overall_score": overall,
        "n_incidents": len(rows),
        "outages": outages,
        "per_region": per_region,
    }


# --------------------------------------------------------------------------- #
def heatmap_data(tenant_id: str) -> Dict[str, Any]:
    """Region × severity grid for the heatmap widget."""
    rows = _fetch_all(tenant_id)
    grid: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        reg = r["metadata"].get("region", "Unknown")
        sev = r["metadata"].get("severity", "unknown")
        grid[reg][sev] += 1
    regions = sorted(grid.keys())
    severities = ["low", "medium", "high", "critical"]
    matrix = [[grid[reg].get(sev, 0) for sev in severities] for reg in regions]
    return {
        "regions": regions,
        "severities": severities,
        "matrix": matrix,
        "n_incidents": len(rows),
    }


# --------------------------------------------------------------------------- #
def timeline_data(tenant_id: str, bucket: str = "day") -> Dict[str, Any]:
    """Chronological incident counts bucketed by day or hour."""
    rows = _fetch_all(tenant_id)
    counts: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        ws = r["metadata"].get("window_start")
        if not ws:
            continue
        try:
            ts = datetime.fromisoformat(ws)
        except (TypeError, ValueError):
            continue
        key = ts.strftime("%Y-%m-%d") if bucket == "day" else ts.strftime("%Y-%m-%d %H:00")
        sev = r["metadata"].get("severity", "unknown")
        counts[key][sev] += 1

    sorted_keys = sorted(counts.keys())
    series = {sev: [counts[k].get(sev, 0) for k in sorted_keys]
              for sev in ("low", "medium", "high", "critical")}
    return {"bucket": bucket, "buckets": sorted_keys, "series": series,
            "n_incidents": len(rows)}


# --------------------------------------------------------------------------- #
def telemetry_summary(tenant_id: str, limit: int = 100) -> Dict[str, Any]:
    """Recent telemetry samples — for live line charts."""
    rows = _fetch_all(tenant_id)
    # Sort by window_start desc, take first `limit`
    def _ts(r):
        ws = r["metadata"].get("window_start") or ""
        return ws
    rows.sort(key=_ts, reverse=True)
    rows = rows[:limit]
    rows.sort(key=_ts)  # back to chronological for charting

    return {
        "samples": [
            {
                "timestamp": r["metadata"].get("window_start"),
                "region": r["metadata"].get("region"),
                "voltage": r["metadata"].get("voltage_mean"),
                "frequency": r["metadata"].get("frequency_mean"),
                "demand": r["metadata"].get("demand_max"),
                "stability": r["metadata"].get("stability_score_mean"),
                "severity": r["metadata"].get("severity"),
            }
            for r in rows
        ],
        "n_samples": len(rows),
    }


# --------------------------------------------------------------------------- #
# Question / recommendation history.
#
# Two layers:
#   - In-memory cache for snappy /recommendations responses (last 100)
#   - Persistent JSONL file at data_processed/qa_history.jsonl so the history
#     survives restarts and is shared across worker processes.
#
# Loaded on app startup via lifespan.py -> load_history(). New entries are
# appended both to memory AND to disk.

import json as _json
from pathlib import Path as _Path

_RECOMMENDATION_CACHE: List[Dict[str, Any]] = []
_CACHE_LIMIT = 100
_HISTORY_PATH = _Path("./data_processed/qa_history.jsonl")


def _persist(item: Dict[str, Any]) -> None:
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(item, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001 — never break /analyze
        logger.warning("qa_history_persist_failed", extra={"err": str(exc)})


def load_history() -> int:
    """Read qa_history.jsonl into the in-memory cache. Returns row count."""
    global _RECOMMENDATION_CACHE
    if not _HISTORY_PATH.exists():
        return 0
    rows: List[Dict[str, Any]] = []
    try:
        with _HISTORY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(_json.loads(line))
                    except Exception:  # tolerate bad lines
                        continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("qa_history_load_failed", extra={"err": str(exc)})
        return 0
    # Keep last _CACHE_LIMIT in memory, newest first
    _RECOMMENDATION_CACHE = list(reversed(rows[-_CACHE_LIMIT:]))
    logger.info("qa_history_loaded", extra={"path": str(_HISTORY_PATH), "count": len(_RECOMMENDATION_CACHE)})
    return len(_RECOMMENDATION_CACHE)


def record_recommendation(item: Dict[str, Any]) -> None:
    """Add a new question/answer to history. Persists to disk."""
    if "ts" not in item:
        item["ts"] = datetime.utcnow().isoformat() + "Z"
    _RECOMMENDATION_CACHE.insert(0, item)
    del _RECOMMENDATION_CACHE[_CACHE_LIMIT:]
    _persist(item)


def recent_recommendations(tenant_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    out = [r for r in _RECOMMENDATION_CACHE
           if r.get("tenant_id", "default") == tenant_id or tenant_id == "default"]
    return out[:limit]


def question_history(tenant_id: str, *, limit: int = 20,
                     unique: bool = True) -> List[Dict[str, Any]]:
    """
    Return previous questions for the FAQ widget.

    When unique=True (default), de-duplicates queries case-insensitively so the
    UI shows the *kind* of questions operators ask, not duplicate text.
    """
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for r in _RECOMMENDATION_CACHE:
        if r.get("tenant_id", "default") != tenant_id and tenant_id != "default":
            continue
        q = (r.get("query") or "").strip()
        if not q:
            continue
        key = q.lower()
        if unique and key in seen:
            continue
        seen.add(key)
        out.append({
            "query":      q,
            "operator":   r.get("operator", "anonymous"),
            "confidence": r.get("confidence", 0),
            "ts":         r.get("ts"),
            "answer":     (r.get("answer") or "")[:200],
        })
        if len(out) >= limit:
            break
    return out


def history_stats(tenant_id: str) -> Dict[str, Any]:
    """Aggregate stats for the FAQ panel header."""
    total = sum(1 for r in _RECOMMENDATION_CACHE
                if r.get("tenant_id", "default") == tenant_id or tenant_id == "default")
    operators = set()
    for r in _RECOMMENDATION_CACHE:
        if r.get("tenant_id", "default") == tenant_id or tenant_id == "default":
            operators.add(r.get("operator", "anonymous"))
    return {
        "total_questions": total,
        "unique_operators": len(operators),
        "history_file": str(_HISTORY_PATH),
        "history_exists": _HISTORY_PATH.exists(),
    }


# --------------------------------------------------------------------------- #
def demand_forecast(tenant_id: str) -> Dict[str, Any]:
    """
    Simple rolling-average demand forecast.
    Groups demand_max by day, computes 3-day rolling average,
    and projects 3 future periods using trend extrapolation.
    """
    import math as _math
    from datetime import timedelta as _td

    rows = _fetch_all(tenant_id)
    daily: Dict[str, list] = defaultdict(list)

    for r in rows:
        ws = r["metadata"].get("window_start")
        if not ws:
            continue
        try:
            ts  = datetime.fromisoformat(ws)
            key = ts.strftime("%Y-%m-%d")
            d   = r["metadata"].get("demand_max")
            if d is not None:
                daily[key].append(float(d))
        except Exception:
            continue

    if not daily:
        return {"actuals": [], "rolling_avg": [], "forecast": [], "n_days": 0}

    sorted_keys = sorted(daily.keys())
    actuals = [(k, round(sum(daily[k]) / len(daily[k]), 3)) for k in sorted_keys]

    WINDOW = 3
    rolling = []
    for i, (k, _) in enumerate(actuals):
        if i < WINDOW - 1:
            rolling.append((k, None))
        else:
            avg = sum(a[1] for a in actuals[max(0, i - WINDOW + 1): i + 1]) / WINDOW
            rolling.append((k, round(avg, 3)))

    # Forecast next 3 days from last rolling avg with a small trend
    last_avg = next((v for _, v in reversed(rolling) if v is not None), None)
    if last_avg is None and actuals:
        last_avg = actuals[-1][1]

    forecasts = []
    if last_avg and sorted_keys:
        try:
            last_dt = datetime.strptime(sorted_keys[-1], "%Y-%m-%d")
        except ValueError:
            last_dt = None
        if last_dt:
            # Simple trend: 1.5 % growth per projected day
            for i in range(1, 4):
                fd     = (last_dt + _td(days=i)).strftime("%Y-%m-%d")
                factor = 1 + 0.015 * i
                forecasts.append({
                    "date":   fd,
                    "demand": round(last_avg * factor, 3),
                    "type":   "forecast",
                })

    # Return last 30 actuals for chart clarity
    tail = actuals[-30:]
    roll_tail = [(k, v) for k, v in rolling[-30:] if v is not None]

    return {
        "actuals":     [{"date": k, "demand": v, "type": "actual"}  for k, v in tail],
        "rolling_avg": [{"date": k, "demand": v, "type": "rolling"} for k, v in roll_tail],
        "forecast":    forecasts,
        "n_days":      len(actuals),
        "unit":        "kW (avg demand_max per day)",
    }


# --------------------------------------------------------------------------- #
def anomaly_correlations(tenant_id: str) -> Dict[str, Any]:
    """
    Pearson correlation matrix between five telemetry signals:
    voltage deviation, frequency deviation, demand, stability, outage events.
    """
    import math as _math

    NOMINAL_V, NOMINAL_F = 230.0, 50.0
    rows = _fetch_all(tenant_id)

    series: Dict[str, List[float]] = {
        "Voltage Dev%": [], "Freq Dev Hz": [],
        "Demand kW":    [], "Stability":   [], "Outage":      [],
    }

    for r in rows:
        m = r["metadata"]
        try:
            v = float(m.get("voltage_mean")        or NOMINAL_V)
            f = float(m.get("frequency_mean")       or NOMINAL_F)
            d = float(m.get("demand_max")           or 0)
            s = float(m.get("stability_score_mean") or 0)
            o = float(m.get("outage_event")         or 0)
        except (TypeError, ValueError):
            continue
        series["Voltage Dev%"].append(round(abs(v - NOMINAL_V) / NOMINAL_V * 100, 4))
        series["Freq Dev Hz"].append(round(abs(f - NOMINAL_F), 4))
        series["Demand kW"].append(d)
        series["Stability"].append(s)
        series["Outage"].append(o)

    n = len(series["Outage"])
    if n < 3:
        return {"metrics": [], "matrix": [], "insights": [], "n_samples": n}

    metrics = list(series.keys())

    def _pearson(x: List[float], y: List[float]) -> float:
        if len(x) < 2:
            return 0.0
        mx, my = sum(x) / len(x), sum(y) / len(y)
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        dx  = _math.sqrt(sum((a - mx) ** 2 for a in x))
        dy  = _math.sqrt(sum((b - my) ** 2 for b in y))
        if dx == 0 or dy == 0:
            return 0.0
        return round(num / (dx * dy), 3)

    matrix = [
        [_pearson(series[m1], series[m2]) for m2 in metrics]
        for m1 in metrics
    ]

    # Top insights: highest off-diagonal correlations
    pairs = []
    for i in range(len(metrics)):
        for j in range(i + 1, len(metrics)):
            corr = matrix[i][j]
            pairs.append((abs(corr), corr, metrics[i], metrics[j]))
    pairs.sort(reverse=True)

    insights = []
    for _, corr, l1, l2 in pairs[:4]:
        direction = "positively" if corr > 0 else "negatively"
        strength  = "strongly" if abs(corr) > 0.6 else "moderately" if abs(corr) > 0.3 else "weakly"
        insights.append(f"{l1} and {l2} are {strength} {direction} correlated (r = {corr:+.3f})")

    return {
        "metrics":    metrics,
        "matrix":     matrix,
        "insights":   insights,
        "n_samples":  n,
    }
