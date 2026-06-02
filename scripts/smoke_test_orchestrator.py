"""
Smoke test for STEP 7 — multi-agent orchestrator.

Exercises the full chain: guardrails -> Retrieval -> Stability -> Failure
-> Recommendation. Prints the agent_trace so you can see what each agent
contributed.

    python scripts/smoke_test_orchestrator.py "voltage drop in south zone"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.agents.orchestrator import AgentOrchestrator  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.rag.bm25_index import BM25Index, build_bm25_index  # noqa: E402


def _bm25():
    cache = Path("data_processed/bm25_index.pkl")
    if cache.exists():
        return BM25Index.load(cache)
    cp = Path("data_processed/chunks.jsonl")
    if not cp.exists():
        return None
    rows = [json.loads(l) for l in cp.read_text().splitlines() if l.strip()]
    return build_bm25_index(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?",
                   default="transformer overloads recurring during evening peak demand")
    p.add_argument("--region", default=None)
    p.add_argument("--severity", default=None)
    p.add_argument("--tenant", default="default")
    args = p.parse_args()

    orch = AgentOrchestrator(settings=get_settings(), bm25_index=_bm25())
    filters = {}
    if args.region: filters["region"] = args.region
    if args.severity: filters["severity"] = args.severity

    out = orch.run(args.query, tenant_id=args.tenant,
                   filters=filters or None)

    print(f"\n=== STATUS: {out['status']}  (provider={out.get('provider', 'n/a')})")
    print(f"=== Duration: {out.get('duration_seconds')}s  Tenant: {out.get('tenant_id')}")
    print("\n--- AGENT TRACE ---")
    for t in out.get("agent_trace", []):
        marker = "✓" if t["status"] == "ok" else "✗"
        print(f"  {marker} {t['agent']:<28} {t['duration_ms']:>6.1f}ms  {t['summary']}")
    print("\n--- STABILITY ANALYSIS ---")
    print(json.dumps(out.get("stability_analysis", {}), indent=2))
    print("\n--- ROOT CAUSES ---")
    for rc in out.get("root_causes", []):
        print(f"  • {rc['cause']} (p={rc['probability']})")
    print("\n--- RECOMMENDATIONS ---")
    for r in out.get("recommendations", []):
        print(f"  • [{r['priority']}] {r['action']}")
    print(f"\n--- ANSWER ({out.get('confidence', 0)}) ---")
    print(out.get("answer", "")[:400])
    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
