# Deployment & Environment Guide

## Environment variables (backend/.env)

```
# LLM (Groq is primary; fallback chain Groq -> Gemini -> OpenAI -> Anthropic -> template)
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=               # get a free key at https://console.groq.com/keys
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=             # optional fallback
GEMINI_MODEL=gemini-1.5-flash
OPENAI_API_KEY=             # optional fallback
ANTHROPIC_API_KEY=          # optional fallback

# Embeddings: 'hash' = offline/zero-dependency (recommended for demo + free hosting).
# Switch to sentence-transformers/all-MiniLM-L6-v2 only on a machine with torch + RAM.
EMBEDDING_MODEL=hash

# Paths
DATA_DIR=./datasets
CHROMA_PERSIST_DIR=../chroma_store
```

If NO LLM key is set, the app uses the deterministic template provider and still
returns Answer + Evidence + Root Cause + Mitigation + Confidence. Nothing breaks.

## Recommended Groq model
- **llama-3.3-70b-versatile** (default): best reasoning quality, ~1-2s latency, reliable for demos.
- llama-3.1-8b-instant: lowest latency, lighter reasoning - use if you want maximum speed.
- deepseek-r1-distill-llama-70b: strong reasoning but slower; not ideal for a live demo.

## Provider fallback order (app/rag/llm.py -> get_provider)
Configured provider first, then groq, gemini, openai, anthropic, finally template.
A provider is only tried if its API key is present; any init/call failure falls
through to the next. No user interruption.

## Local run
See RUN_GUIDE.md. Summary:
- backend: `py -3.11 -m venv venv; venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --port 8000`
- frontend: `npm install; npm run dev`
Data auto-loads at startup; no ETL click required.

## Render deployment (render.yaml is ready)
- Backend uses `$PORT`, `--host 0.0.0.0`, health check `/api/v1/health`, persistent disk at `/var/data`.
- Set secrets in the Render dashboard: GROQ_API_KEY (and optionally GEMINI/OPENAI), JWT_SECRET.
- Frontend static site uses `VITE_API_URL=https://<your-backend>.onrender.com`.
- EMBEDDING_MODEL is set to `hash` in render.yaml (free tier has 512MB RAM and OOMs on torch/MiniLM).

### IMPORTANT Render note - dataset availability
`datasets/*.csv` is git-ignored, so the CSV is NOT in the deployed repo. On Render,
startup auto-ingest will find no dataset. Choose ONE:
1. Upload `smart_grid_stability_augmented.csv` to the persistent disk at
   `/var/data/datasets/` (via a one-off Render shell), OR
2. Un-ignore and commit `backend/datasets/smart_grid_stability_augmented.csv`
   (14 MB - acceptable) so it ships with the build.
Locally this is a non-issue (the CSV is already in backend/datasets).

## What was intentionally NOT changed (stability over scope)
- FAISS and embedding-model hot-swap: the UI exposes the dropdowns, but only
  ChromaDB + the current embedder are wired. Implementing a full FAISS/embedding
  abstraction is high-risk for a same-day demo and adds no demo value over the
  working Chroma+BM25 hybrid. The dropdowns note "Re-Ingest required".
- All existing dashboard/telemetry/failure/recommendation/chat/API functionality
  is unchanged and verified working.
