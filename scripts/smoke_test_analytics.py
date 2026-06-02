"""
Smoke test for STEP 8 — analytics endpoints' service layer.

Calls each analytics function (grid_health_score, heatmap_data, timeline_data,
telemetry_summary) directly against the Chroma collection populated by STEP 4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services import analytics_service as svc  # noqa: E402


def main() -> int:
    tenant = "default"

    print("=== GRID HEALTH SCORE ===")
    g = svc.grid_health_score(tenant)
    print(json.dumps({k: v for k, v in g.items() if k != "per_region"}, indent=2))
    print(f"per_region (top 5): {dict(list(g.get('per_region', {}).items())[:5])}")

    print("\n=== HEATMAP ===")
    h = svc.heatmap_data(tenant)
    print(f"regions: {h['regions'][:5]}  severities: {h['severities']}")
    print(f"matrix rows: {len(h['matrix'])}")
    for r, row in zip(h["regions"][:3], h["matrix"][:3]):
        print(f"  {r:<15} {row}")

    print("\n=== TIMELINE (day) ===")
    t = svc.timeline_data(tenant, bucket="day")
    print(f"buckets: {len(t['buckets'])}  first: {t['buckets'][:3]}")
    for sev, series in t["series"].items():
        if any(series):
            print(f"  {sev}: total={sum(series)} max={max(series)}")

    print("\n=== TELEMETRY (last 5) ===")
    tel = svc.telemetry_summary(tenant, limit=5)
    print(f"samples: {tel['n_samples']}")
    for s in tel["samples"][:5]:
        print(f"  {s.get('timestamp')} {s.get('region')} V={s.get('voltage')} "
              f"F={s.get('frequency')} sev={s.get('severity')}")

    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
