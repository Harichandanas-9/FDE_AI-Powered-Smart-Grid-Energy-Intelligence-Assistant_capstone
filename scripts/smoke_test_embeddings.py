"""
Smoke test for STEP 4 — embeds the first N chunks from data_processed/chunks.jsonl
into Chroma and reports the collection size.

Usage:
    python scripts/smoke_test_embeddings.py              # embed all chunks
    python scripts/smoke_test_embeddings.py --limit 200  # only first 200

Requires:
    pip install -r backend/requirements-ml.txt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.rag.embeddings import embed_texts  # noqa: E402
from app.rag.vector_store import (  # noqa: E402
    count,
    get_client,
    get_or_create_collection,
    reset_collection,
    upsert_chunks,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="data_processed/chunks.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate the collection first")
    args = parser.parse_args()

    settings = get_settings()
    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        print(f"[smoke] chunks file not found: {chunks_path}", file=sys.stderr)
        print("[smoke] Run STEP 3 first: python scripts/smoke_test_ingestion.py")
        return 1

    rows = []
    with chunks_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if args.limit:
        rows = rows[: args.limit]
    print(f"[smoke] loaded {len(rows)} chunks from {chunks_path}")

    client = get_client(settings.chroma_persist_dir)
    if args.reset:
        reset_collection(client)
    collection = get_or_create_collection(client)
    print(f"[smoke] collection ready at {settings.chroma_persist_dir}")

    t0 = time.time()
    ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]
    metadatas = [r.get("metadata", {}) for r in rows]

    # Embed in chunks of 256 for memory safety
    total = 0
    BATCH = 256
    for s in range(0, len(texts), BATCH):
        e = s + BATCH
        embs = embed_texts(texts[s:e], model_name=settings.embedding_model)
        total = upsert_chunks(collection, ids[s:e], texts[s:e], embs, metadatas[s:e])
        print(f"[smoke]  upserted {min(e, len(texts))}/{len(texts)}, collection={total}")
    dur = time.time() - t0

    print(f"\n[smoke] DONE in {dur:.1f}s, collection has {count(collection)} vectors")
    print(f"[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
