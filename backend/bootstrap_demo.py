"""
One-shot demo bootstrap + diagnostic.

Run this ONCE from the backend/ folder with the venv active:

    python bootstrap_demo.py

It loads the Smart Grid Stability dataset, builds the BM25 index, embeds into
ChromaDB, and prints a clear PASS/FAIL for every stage. If anything fails you
get the FULL traceback right here in the terminal (file + line + exception),
so we can see the real error instead of a truncated UI toast.

It is safe to run repeatedly. It does NOT require the web server to be running.
"""
import sys, time, traceback, json
from pathlib import Path

def stage(name):
    print(f"\n[{time.strftime('%H:%M:%S')}] === {name} ===", flush=True)

def ok(msg):   print(f"   PASS  {msg}", flush=True)
def fail(msg): print(f"   FAIL  {msg}", flush=True)

def main():
    t0 = time.time()
    stage("ETL STARTED")
    try:
        from app.api.routes_datasets import _data_dir
        from app.data.ingestion_pipeline import run_ingestion
        from app.rag.bm25_index import build_bm25_index
        ok("imports loaded")
    except Exception:
        fail("import error"); traceback.print_exc(); sys.exit(1)

    stage("DATASET DISCOVERY")
    try:
        d = _data_dir()
        csvs = sorted(p.name for p in Path(d).glob("*.csv"))
        print(f"   datasets dir: {d}")
        print(f"   CSVs found  : {csvs}")
        if not csvs:
            fail("no CSV files in datasets dir — copy smart_grid_stability_augmented.csv there")
            sys.exit(1)
        ok(f"{len(csvs)} dataset(s) discovered")
    except Exception:
        fail("dataset discovery error"); traceback.print_exc(); sys.exit(1)

    stage("INGESTION (CSV -> chunks.jsonl)")
    try:
        report = run_ingestion(data_dir=_data_dir(), sources=["stability"])
        print(f"   chunks_written: {report.chunks_written}")
        print(f"   output_path   : {report.output_path}")
        if report.errors:
            print(f"   ingest errors : {report.errors}")
        if not report.chunks_written:
            fail("0 chunks written — see ingest errors above"); sys.exit(1)
        ok(f"{report.chunks_written} chunks written in {report.duration_seconds:.2f}s")
    except Exception:
        fail("ingestion error"); traceback.print_exc(); sys.exit(1)

    stage("READ chunks.jsonl")
    try:
        rows = []
        with Path(report.output_path).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().strip("\x00")
                if line:
                    try: rows.append(json.loads(line))
                    except Exception: pass
        ok(f"{len(rows)} valid rows read")
    except Exception:
        fail("read error"); traceback.print_exc(); sys.exit(1)

    stage("BM25 INDEX (keyword search backbone)")
    try:
        bm25 = build_bm25_index(rows)
        bm25.save(Path(report.output_path).parent / "bm25_index.pkl")
        ok(f"BM25 built + saved ({len(rows)} docs)")
    except Exception:
        fail("BM25 error"); traceback.print_exc()

    stage("CHROMADB EMBED + WRITE (best-effort)")
    try:
        from app.core.config import get_settings
        from app.rag.embeddings import embed_texts
        from app.rag.vector_store import get_client, get_or_create_collection, upsert_chunks
        s = get_settings()
        client = get_client(s.chroma_persist_dir)
        col = get_or_create_collection(client)
        BATCH = 512; total = 0
        for i in range(0, len(rows), BATCH):
            sub = rows[i:i+BATCH]
            embs = embed_texts([r["text"] for r in sub], model_name="hash", batch_size=512)
            total = upsert_chunks(col, [r["id"] for r in sub],
                                  [r["text"] for r in sub], embs,
                                  [r.get("metadata", {}) for r in sub])
        ok(f"ChromaDB now holds {total} vectors")
    except Exception:
        fail("ChromaDB failed — NOT fatal; app still works on BM25+JSONL")
        traceback.print_exc()

    stage("ETL COMPLETED")
    print(f"\n   Total time: {time.time()-t0:.2f}s")
    print("   Data is ready. Start the server (uvicorn app.main:app --port 8000) and open the app.\n")

if __name__ == "__main__":
    main()
