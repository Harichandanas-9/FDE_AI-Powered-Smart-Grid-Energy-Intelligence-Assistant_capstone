"""
Smoke test for STEP 6 — full /analyze pipeline.

Goes end-to-end: guardrails -> hybrid retrieve -> LLM (or template fallback)
-> structured response. No API key required (template fallback covers it).

    python scripts/smoke_test_analyze.py "voltage instability in south zone"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.rag.bm25_index import BM25Index, build_bm25_index  # noqa: E402
from app.rag.rag_pipeline import RagPipeline  # noqa: E402


def _bm25() -> BM25Index | None:
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
                   default="Voltage instability is increasing in South Zone during evening peak demand. What are the likely causes?")
    p.add_argument("--region", default=None)
    p.add_argument("--severity", default=None)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--tenant", default="default")
    args = p.parse_args()

    pipe = RagPipeline(settings=get_settings(), bm25_index=_bm25())

    where = {}
    if args.region: where["region"] = args.region
    if args.severity: where["severity"] = args.severity

    out = pipe.run(args.query, where=where or None, top_k=args.top_k,
                   tenant_id=args.tenant)

    print("=== status:", out.get("status"))
    print("=== provider:", out.get("provider"))
    print("=== tenant:", out.get("tenant_id"))
    print("=== confidence:", out.get("confidence"))
    print("\n--- ANSWER ---")
    print(out.get("answer"))
    print("\n--- REASONING ---")
    print(out.get("reasoning"))
    print("\n--- ROOT CAUSES ---")
    for rc in out.get("root_causes", []):
        print(f"  • {rc['cause']} (p={rc['probability']}) ev={rc['evidence']}")
    print("\n--- RECOMMENDATIONS ---")
    for r in out.get("recommendations", []):
        print(f"  • [{r['priority']}] {r['action']}")
        print(f"        rationale: {r['rationale']}")
    print(f"\n--- RETRIEVED ({len(out.get('retrieved', []))}) ---")
    for c in out.get("retrieved", [])[:3]:
        print(f"  {c['id']} score={c['score']:.4f}")
    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
