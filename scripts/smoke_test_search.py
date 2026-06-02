"""
Smoke test for STEP 5 — hybrid search.

Runs the same query through Chroma, BM25, and the RRF fusion, prints the
top results. Assumes STEP 3 + STEP 4 have already run.

    python scripts/smoke_test_search.py "voltage instability in south zone"
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
from app.rag.hybrid_retriever import HybridRetriever  # noqa: E402


def _load_or_build_bm25() -> BM25Index:
    cache = Path("data_processed/bm25_index.pkl")
    if cache.exists():
        print(f"[smoke] loading BM25 from {cache}")
        return BM25Index.load(cache)
    chunks_path = Path("data_processed/chunks.jsonl")
    if not chunks_path.exists():
        raise SystemExit("[smoke] no chunks.jsonl — run STEP 3 first")
    rows = [json.loads(l) for l in chunks_path.read_text().splitlines() if l.strip()]
    idx = build_bm25_index(rows)
    idx.save(cache)
    print(f"[smoke] built BM25 over {len(rows)} chunks, cached to {cache}")
    return idx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?",
                        default="voltage instability and transformer overload during evening peak")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--region", default=None)
    parser.add_argument("--severity", default=None)
    args = parser.parse_args()

    settings = get_settings()
    bm25 = _load_or_build_bm25()
    retr = HybridRetriever(settings, bm25_index=bm25)

    where = {}
    if args.region: where["region"] = args.region
    if args.severity: where["severity"] = args.severity

    print(f"\n[smoke] QUERY: {args.query!r}")
    print(f"[smoke] FILTERS: {where or 'none'}\n")
    hits = retr.retrieve(args.query, top_k=args.top_k, where=where or None)
    if not hits:
        print("[smoke] NO RESULTS — check that Chroma has data (run STEP 4)")
        return 1

    for rank, c in enumerate(hits, 1):
        print(f"#{rank}  score={c.score:.4f}  sem_rank={c.semantic_rank}  "
              f"kw_rank={c.keyword_rank}")
        print(f"     id      = {c.id}")
        print(f"     region  = {c.metadata.get('region')}  | severity = "
              f"{c.metadata.get('severity')}  | source = "
              f"{c.metadata.get('source_dataset')}")
        print(f"     text    = {c.text[:140]}...")
        print()
    print("[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
