"""
Quick demo data setup — bypasses ETL, populates ChromaDB in ~5s.
Run from backend/ folder with venv active:
    python setup_demo_data.py
"""
import sys, os, json, re, hashlib, datetime, pathlib, shutil
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

print("Smart Grid AI — Quick Data Setup")
print("=" * 40)

import numpy as np
import pandas as pd

def hash_embed(texts, dim=384):
    TOKEN = re.compile(r"[a-z][a-z0-9-]+")
    arr = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        toks = TOKEN.findall(text.lower())
        for t in toks:
            arr[i, int(hashlib.md5(t.encode()).hexdigest(), 16) % dim] += 1.0
        for a, b in zip(toks, toks[1:]):
            arr[i, int(hashlib.md5((a+"_"+b).encode()).hexdigest(), 16) % dim] += 0.5
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (arr / norms).tolist()

def sanitize_meta(m):
    out = {}
    for k, v in (m or {}).items():
        if v is None: continue
        if isinstance(v, bool): out[k] = v
        elif isinstance(v, int): out[k] = v
        elif isinstance(v, float): out[k] = v
        elif isinstance(v, str): out[k] = v
        else:
            try: out[k] = str(v)
            except: pass
    return out or {"_ok": "1"}

try:
    from app.utils.paths import resolve_dir, _find_project_root
    from app.core.config import get_settings
    from app.data.loader import discover_datasets
    from app.data.normalizer import normalize
    from app.data.cleaner import clean
    from app.data.aggregator import aggregate
    from app.data.templater import render_dataframe, chunk_to_dict
    settings = get_settings()
except Exception as e:
    print("ERROR importing app modules:", e)
    sys.exit(1)

# Find CSV
data_dir = resolve_dir(settings.data_dir, create=False)
if not any(data_dir.glob("*.csv")):
    root = _find_project_root()
    if root:
        data_dir = root / "datasets"

found = discover_datasets(data_dir)
stability = [(p, k) for p, k in found if k == "stability"]
if not stability:
    print("ERROR: smart_grid_stability_augmented.csv not found in", data_dir)
    sys.exit(1)

csv_path = stability[0][0]
print(f"Step 1/4: Loading 100 rows from {csv_path.name} ...", end=" ", flush=True)
try:
    df_raw   = pd.read_csv(csv_path, nrows=100)
    df_norm  = normalize(df_raw, "stability")
    df_clean = clean(df_norm)
    df_agg   = aggregate(df_clean)
    df_ch    = render_dataframe(df_agg)
    chunks   = [chunk_to_dict(row, tenant_id="default") for _, row in df_ch.iterrows()]
    print(f"done — {len(chunks)} chunks")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

print(f"Step 2/4: Embedding with HashEmbedder ...", end=" ", flush=True)
texts      = [c["text"] for c in chunks]
embeddings = hash_embed(texts)
print("done")

# IMPORTANT: Delete old chroma_store to remove any locks/corruption
chroma_dir = resolve_dir(settings.chroma_persist_dir, create=False)
print(f"Step 3/4: Resetting ChromaDB at {chroma_dir} ...", end=" ", flush=True)
try:
    if chroma_dir.exists():
        shutil.rmtree(str(chroma_dir), ignore_errors=True)
        print(f"old store deleted ...", end=" ", flush=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_or_create_collection("grid_incidents", metadata={"hnsw:space": "cosine"})
    
    ids   = [c["id"] for c in chunks]
    metas = [sanitize_meta(c.get("metadata", {})) for c in chunks]
    
    # Small batches to avoid memory issues
    BATCH = 10
    for s in range(0, len(ids), BATCH):
        col.upsert(
            ids=ids[s:s+BATCH],
            documents=texts[s:s+BATCH],
            embeddings=embeddings[s:s+BATCH],
            metadatas=metas[s:s+BATCH],
        )
    count = col.count()
    print(f"done — {count} vectors")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print(f"Step 4/4: Writing ETL history ...", end=" ", flush=True)
try:
    hist = resolve_dir("./data_processed", create=True) / "etl_history.jsonl"
    record = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "filename": "smart_grid_stability_augmented.csv",
        "source_key": "stability", "tenant_id": "default",
        "operator": "setup_script", "chunks_written": len(chunks),
        "vectors_total": count, "duration_seconds": 5.0, "errors": [],
    }
    hist.write_text(json.dumps(record) + "\n", encoding="utf-8")
    print("done")
except Exception as e:
    print(f"FAILED: {e}")

print()
print("SUCCESS! Vectors in ChromaDB:", count)
print()
print("Now run:")
print("  uvicorn app.main:app --reload --port 8000")
print("Then open: http://localhost:5173")
print("Dashboard shows real data. No ETL run needed!")
