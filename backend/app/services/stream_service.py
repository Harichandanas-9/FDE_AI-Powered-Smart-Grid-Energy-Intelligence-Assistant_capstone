"""
Telemetry simulator for /ws/telemetry.

Two modes:
  1. replay   — replays rows from data_processed/chunks.jsonl at 1 tick/sec
                (so the panel sees the actual ingested data scrolling by).
  2. synthetic — generates plausible noise around nominal values; used when
                no chunks file is present yet.

Each tick is one JSON message:
    {timestamp, region, voltage, frequency, demand, stability, severity,
     source_dataset}
"""
from __future__ import annotations

import asyncio
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

REGIONS = ["North Zone", "South Zone", "East Zone", "West Zone", "Central Hub"]
SEVERITIES = ["low", "medium", "high", "critical"]
NOM_V, NOM_F = 230.0, 50.0


def _classify(v_dev: float, f_dev: float) -> str:
    """Classify severity from normalized voltage deviation and absolute frequency deviation."""
    if v_dev > 0.10 or f_dev > 1.5: return "critical"
    if v_dev > 0.06 or f_dev > 0.8: return "high"
    if v_dev > 0.03 or f_dev > 0.3: return "medium"
    return "low"


def _synthesize(i: int) -> dict:
    """Generate a single synthetic telemetry tick using sinusoidal patterns with noise."""
    region = REGIONS[i % len(REGIONS)]
    # smooth oscillation + small jitter
    v = NOM_V + 8 * math.sin(i / 12) + random.uniform(-4, 4)
    f = NOM_F + 0.4 * math.sin(i / 9 + 1) + random.uniform(-0.2, 0.2)
    d = 5.0 + 3 * math.sin(i / 18) + random.uniform(0, 1.5)
    s = (NOM_V - abs(v - NOM_V)) / NOM_V * 0.6  # synth stability in [-1, 1]
    v_dev = abs(v - NOM_V) / NOM_V
    f_dev = abs(f - NOM_F)
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "region": region,
        "voltage": round(v, 2),
        "frequency": round(f, 3),
        "demand": round(d, 2),
        "stability": round(s, 3),
        "severity": _classify(v_dev, f_dev),
        "source_dataset": "synthetic",
    }


def _from_chunk(chunk: dict) -> dict:
    """Extract telemetry fields from a stored chunk dict for replay mode."""
    m = chunk.get("metadata", {})
    return {
        "timestamp": m.get("window_start") or datetime.utcnow().isoformat() + "Z",
        "region": m.get("region", "Unknown"),
        "voltage": m.get("voltage_mean"),
        "frequency": m.get("frequency_mean"),
        "demand": m.get("demand_max"),
        "stability": m.get("stability_score_mean"),
        "severity": m.get("severity", "unknown"),
        "source_dataset": m.get("source_dataset", "unknown"),
    }


def _load_replay() -> list[dict]:
    """Load all chunks from chunks.jsonl as replay-ready telemetry dicts."""
    p = Path("data_processed/chunks.jsonl")
    if not p.exists():
        return []
    rows = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(_from_chunk(json.loads(line)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("replay_load_failed", extra={"err": str(exc)})
    return rows


async def stream_telemetry(
    *, mode: str = "auto", interval_sec: float = 1.0,
    limit: Optional[int] = None,
) -> AsyncIterator[dict]:
    """
    Yields telemetry ticks forever (or up to `limit`).
    mode: "auto" | "replay" | "synthetic"
    """
    replay_data = _load_replay() if mode in ("auto", "replay") else []
    use_replay = bool(replay_data) and mode != "synthetic"
    logger.info(
        "stream_started",
        extra={"mode": "replay" if use_replay else "synthetic",
               "rows": len(replay_data), "interval_sec": interval_sec},
    )

    i = 0
    while limit is None or i < limit:
        if use_replay:
            tick = dict(replay_data[i % len(replay_data)])
            tick["timestamp"] = datetime.utcnow().isoformat() + "Z"
        else:
            tick = _synthesize(i)
        yield tick
        i += 1
        await asyncio.sleep(interval_sec)
