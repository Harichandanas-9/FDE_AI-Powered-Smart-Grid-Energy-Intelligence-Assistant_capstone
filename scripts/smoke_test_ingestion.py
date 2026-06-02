"""
Smoke test for STEP 3 — runs the ingestion pipeline on whatever CSVs you've
dropped into datasets/ and prints a summary.

Usage (from project root, with backend venv activated):

    python scripts/smoke_test_ingestion.py
    python scripts/smoke_test_ingestion.py --sources stability
    python scripts/smoke_test_ingestion.py --max-rows household=20000

Exits 0 on success, 1 if no chunks were produced.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make backend.app importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.data.ingestion_pipeline import run_ingestion  # noqa: E402


def parse_max_rows(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not v:
            raise SystemExit(f"invalid --max-rows entry: {it!r} (expected key=value)")
        out[k] = int(v)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="*", help="filter, e.g. stability household")
    parser.add_argument("--max-rows", nargs="*", default=[],
                        help="per-source row caps, e.g. household=50000")
    args = parser.parse_args()

    report = run_ingestion(
        sources=args.sources,
        max_rows_override=parse_max_rows(args.max_rows),
    )
    print(json.dumps(report.to_dict(), indent=2))
    if report.chunks_written == 0:
        print("\n[smoke] NO CHUNKS WRITTEN — check datasets/ folder", file=sys.stderr)
        return 1

    # Show a sample
    out = Path(report.output_path)
    if out.exists():
        with out.open() as f:
            first = f.readline().strip()
        print("\n[smoke] First chunk:")
        print(json.dumps(json.loads(first), indent=2))

    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
