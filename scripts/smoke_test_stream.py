"""Smoke test for STEP 13 — synthetic telemetry generator."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.stream_service import stream_telemetry  # noqa: E402


async def main() -> int:
    print("=== Synthetic stream (5 ticks @ 50 ms) ===")
    n = 0
    async for tick in stream_telemetry(mode="synthetic", interval_sec=0.05, limit=5):
        print(f"  {tick['timestamp'][:19]} {tick['region']:<12} "
              f"V={tick['voltage']:>6.2f} F={tick['frequency']:>5.2f} "
              f"sev={tick['severity']}")
        n += 1
    assert n == 5
    print("[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
