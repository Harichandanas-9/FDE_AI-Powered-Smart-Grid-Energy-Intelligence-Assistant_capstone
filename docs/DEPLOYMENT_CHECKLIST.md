# Deployment Checklist — AI-Powered Smart Grid Energy Intelligence Assistant

> Platform: Render (free tier)
> Backend: FastAPI (Python 3.11), Web Service + Persistent Disk
> Frontend: React + Vite, Static Site
> Last updated: June 2026

---

## Pre-Deployment Checklist

Complete all items in this section before creating services on Render.

### Secrets and API Keys

- [ ] `OPENAI_API_KEY` obtained from https://platform.openai.com/api-keys
- [ ] `ANTHROPIC_API_KEY` obtained (optional — only needed if `LLM_PROVIDER=anthropic`)
- [ ] `JWT_SECRET` generated: must be at minimum 32 random characters

  ```
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

- [ ] Secrets stored in a password manager — never committed to git

### Repository Checks

- [ ] `render.yaml` present at repo root and contains both `smart-grid-backend` and `smart-grid-frontend` service definitions
- [ ] `backend/requirements.txt` and `backend/requirements-ml.txt` both present
- [ ] `backend/runtime.txt` present with content `python-3.11.10`
- [ ] `frontend/package.json` present with `"build": "vite build"` script
- [ ] `backend/.env` is listed in `.gitignore` (do NOT commit .env to git)
- [ ] No hardcoded API keys in any source file

### Local Smoke Test

- [ ] Backend starts locally: `cd backend && uvicorn app.main:app --port 8000`
- [ ] `GET http://localhost:8000/api/v1/health` returns `{"status": "ok", ...}`
- [ ] Frontend builds locally: `cd frontend && npm ci && npm run build`
- [ ] `dist/` folder created with `index.html`

---

## Backend Deployment on Render

### Step 1 — Create Web Service

1. In Render dashboard → New → Web Service
2. Connect your GitHub repository
3. Configure:

   | Field | Value |
   |---|---|
   | Name | `smart-grid-backend` |
   | Region | Oregon (US West) |
   | Branch | `main` |
   | Root Directory | `backend` |
   | Runtime | Python 3 |
   | Build Command | `pip install --upgrade pip && pip install -r requirements.txt && pip install -r requirements-ml.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Plan | Free |

4. Set Health Check Path: `/api/v1/health`
5. Enable Auto-Deploy: Yes

### Step 2 — Add Persistent Disk

1. In the backend service settings → Disks → Add Disk
2. Configure:

   | Field | Value |
   |---|---|
   | Name | `chroma-disk` |
   | Mount Path | `/var/data` |
   | Size | 1 GB |

The persistent disk is required for:
- `CHROMA_PERSIST_DIR=/var/data/chroma_store` — ChromaDB vectors survive service restarts
- `DATA_DIR=/var/data/datasets` — uploaded CSV files persist

### Step 3 — Set Environment Variables

Set the following in the Render backend service → Environment tab.

**Do NOT use the `render.yaml` sync field for secrets — set them manually in the dashboard.**

| Variable | Value | Required |
|---|---|---|
| `APP_ENV` | `production` | Yes |
| `APP_LOG_LEVEL` | `INFO` | Yes |
| `DATA_DIR` | `/var/data/datasets` | Yes |
| `CHROMA_PERSIST_DIR` | `/var/data/chroma_store` | Yes |
| `CORS_ORIGINS` | `https://smart-grid-frontend.onrender.com,http://localhost:5173` | Yes |
| `LLM_PROVIDER` | `openai` | Yes |
| `LLM_MODEL` | `gpt-4o-mini` | Yes |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Yes |
| `RETRIEVAL_TOP_K` | `20` | Yes |
| `FINAL_TOP_K` | `5` | Yes |
| `MULTI_TENANCY_ENABLED` | `false` | Yes |
| `JWT_SECRET` | (32+ char random string) | Yes — set in dashboard |
| `OPENAI_API_KEY` | (your key) | Yes — set in dashboard |
| `ANTHROPIC_API_KEY` | (your key) | No (optional) |
| `PYTHON_VERSION` | `3.11.10` | Yes |

Optional tuning variables:

| Variable | Default | Notes |
|---|---|---|
| `RRF_SEMANTIC_WEIGHT` | `0.6` | Weight for ChromaDB semantic leg in RRF fusion |
| `RRF_KEYWORD_WEIGHT` | `0.4` | Weight for BM25 keyword leg in RRF fusion |
| `RERANKER_ENABLED` | `false` | Set to `true` to enable cross-encoder reranking (slower) |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Only used when RERANKER_ENABLED=true |
| `JWT_ALGORITHM` | `HS256` | Do not change unless you know what you are doing |
| `JWT_EXPIRY_MINUTES` | `480` | Session length in minutes |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Only relevant when LLM_PROVIDER=ollama |

### Step 4 — Deploy Backend

1. Click "Create Web Service"
2. Monitor the build log — expected build time: 3–6 minutes (ML dependencies are large)
3. Wait for the service status to show "Live"
4. Test: `curl https://smart-grid-backend.onrender.com/api/v1/health`

Expected response:
```json
{
  "status": "ok",
  "version": "...",
  "components": {
    "api": "ok",
    "config": "ok",
    "logging": "ok",
    "ingestion": "not_run",
    "chroma": "not_initialized",
    "embeddings": "not_initialized",
    "bm25": "not_initialized",
    "llm": "configured",
    "auth": "disabled"
  }
}
```

`"not_run"` and `"not_initialized"` are **healthy** states — they mean the system is ready and waiting for ETL to be triggered.

---

## Frontend Deployment on Render

### Step 5 — Create Static Site

1. In Render dashboard → New → Static Site
2. Connect same GitHub repository
3. Configure:

   | Field | Value |
   |---|---|
   | Name | `smart-grid-frontend` |
   | Branch | `main` |
   | Root Directory | `frontend` |
   | Build Command | `npm ci && npm run build` |
   | Publish Directory | `dist` |

4. Under Redirects/Rewrites, add a catch-all rewrite rule:
   - Source: `/*`
   - Destination: `/index.html`
   - Type: Rewrite

   This is required for React Router client-side routing to work on direct URL navigation.

### Step 6 — Set Frontend Environment Variables

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://smart-grid-backend.onrender.com` |

Note: In Vite, only variables prefixed with `VITE_` are exposed to the browser bundle. The `api.js` service layer reads `import.meta.env.VITE_API_URL`.

### Step 7 — Deploy Frontend

1. Click "Create Static Site"
2. Monitor build log — expected build time: 30–60 s
3. Wait for status "Live"
4. Open: `https://smart-grid-frontend.onrender.com`

---

## Post-Deployment Verification

### Health Check

```bash
curl https://smart-grid-backend.onrender.com/api/v1/health
```

All components should show `ok`, `not_run`, `not_initialized`, `configured`, or `disabled`.
No component should show `error`.

### Run ETL

1. Open the frontend in a browser
2. Navigate to the **ETL** page (`/etl`)
3. Click "Run ETL" for `smart_grid_stability_augmented`
4. Wait for completion (30–90 seconds — first run downloads the MiniLM model ~80 MB)
5. Status should show chunks written > 0

Or via API:
```bash
curl -X POST https://smart-grid-backend.onrender.com/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"sources": ["smart_grid_stability"]}'
```

### Run Embed

After ETL, embed the chunks into ChromaDB:
```bash
curl -X POST https://smart-grid-backend.onrender.com/api/v1/embed \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Test Query

```bash
curl -X POST https://smart-grid-backend.onrender.com/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "What causes transformer overload in the North Zone?"}'
```

Expected: response with `"status": "ok"`, non-empty `"recommendations"`, `"agent_trace"` with 5 entries.

### Test Predictive Endpoint

```bash
curl https://smart-grid-backend.onrender.com/api/v1/predict
```

Expected: `{"status": "ok", "overall": {...}, "per_region": {...}, "global_alerts": [...]}`

### Test WebSocket

From browser console on the deployed frontend URL:
```javascript
const ws = new WebSocket('wss://smart-grid-backend.onrender.com/api/v1/ws/telemetry?mode=auto&rate=2');
ws.onmessage = e => console.log(JSON.parse(e.data));
```

Expected: JSON ticks arriving every 0.5 s with voltage, frequency, stability fields.

---

## Common Issues and Fixes

### Build Fails: `torch` DLL Error on Windows Local
**Symptom**: `OSError: [WinError 126] The specified module could not be found` during embedding model load.
**Fix**: This is handled automatically — the system falls back to `HashEmbedder` (pure NumPy). No action needed. The health endpoint will show `"embeddings": "hash-fallback"`.

### Build Fails: `ResolutionImpossible` for ML Dependencies
**Symptom**: `pip` fails to resolve `langchain` + `numpy` + `chromadb` on Python 3.13.
**Fix**: Ensure `backend/runtime.txt` contains `python-3.11.10`. The `requirements-ml.txt` pins use loose ranges tested on Python 3.11.

### Frontend Shows "API Unavailable"
**Symptom**: All dashboard cards show error state.
**Cause**: `VITE_API_URL` is not set, or points to `localhost` in production.
**Fix**: In Render Static Site → Environment → set `VITE_API_URL=https://smart-grid-backend.onrender.com`.

### Dashboard Shows "ETL Yet To Run" After ETL Completed
**Symptom**: Dashboard KPI cards show 0 or "Yet To Run" despite ETL succeeding.
**Cause**: Axios cache serving stale ETL status.
**Fix**: Hard-refresh the browser (Ctrl+Shift+R). The ETL page appends a `_t` cache-busting parameter; if the issue persists, check that the backend's `/api/v1/ingest/status` returns `last_run` with a timestamp.

### Render Free Tier Cold Start (502 on First Request)
**Symptom**: First request after 15 minutes of inactivity returns 502.
**Cause**: Render free tier spins down idle services.
**Fix**: Expected behavior on free tier. The service restarts in ~30 s. For a demo, send a warmup request to `/api/v1/health` before the presentation.

### ChromaDB Data Lost After Redeploy
**Symptom**: After a new deploy, ChromaDB is empty.
**Cause**: The persistent disk was not configured, or the `CHROMA_PERSIST_DIR` env var points to the ephemeral filesystem.
**Fix**: Verify `CHROMA_PERSIST_DIR=/var/data/chroma_store` and that the disk is mounted at `/var/data`. Re-run ETL + Embed.

### CORS Error in Browser
**Symptom**: Browser console shows `CORS policy: No 'Access-Control-Allow-Origin' header`.
**Cause**: Frontend URL not in `CORS_ORIGINS`.
**Fix**: Update `CORS_ORIGINS` env var on the backend to include the full frontend URL (e.g., `https://smart-grid-frontend.onrender.com`).

### JWT Errors (`401 Unauthorized`)
**Symptom**: All API calls return 401.
**Cause**: `MULTI_TENANCY_ENABLED=true` but the frontend is not sending an Authorization header.
**Fix**: Either set `MULTI_TENANCY_ENABLED=false` (single-tenant mode) or log in via `POST /api/v1/auth/login` and include the Bearer token.

---

## Environment Variable Reference Table

| Variable | Default | Required | Description |
|---|---|---|---|
| `APP_ENV` | `development` | Yes | `development` or `production` |
| `APP_HOST` | `0.0.0.0` | No | Bind address (uvicorn) |
| `APP_PORT` | `8000` | No | Port (overridden by Render's `$PORT`) |
| `APP_LOG_LEVEL` | `INFO` | No | Logging verbosity |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Yes | Comma-separated allowed origins |
| `DATA_DIR` | `./datasets` | Yes | Path to CSV source files |
| `CHROMA_PERSIST_DIR` | `./chroma_store` | Yes | ChromaDB persistence directory |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | No | HuggingFace model ID |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | No | Cross-encoder model (if enabled) |
| `RERANKER_ENABLED` | `false` | No | Enable cross-encoder reranking |
| `LLM_PROVIDER` | `openai` | Yes | `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | `gpt-4o-mini` | Yes | Model identifier for the chosen provider |
| `OPENAI_API_KEY` | _(empty)_ | Conditional | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | _(empty)_ | Conditional | Required if `LLM_PROVIDER=anthropic` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | No | Required if `LLM_PROVIDER=ollama` |
| `RETRIEVAL_TOP_K` | `20` | No | Number of candidates per retriever leg |
| `FINAL_TOP_K` | `5` | No | Number of chunks passed to the LLM |
| `RRF_SEMANTIC_WEIGHT` | `0.6` | No | RRF weight for semantic leg |
| `RRF_KEYWORD_WEIGHT` | `0.4` | No | RRF weight for BM25 leg |
| `MULTI_TENANCY_ENABLED` | `false` | No | Enable JWT-based tenant isolation |
| `JWT_SECRET` | `change-me-in-production-...` | Yes (prod) | HS256 signing secret, min 32 chars |
| `JWT_ALGORITHM` | `HS256` | No | JWT signing algorithm |
| `JWT_EXPIRY_MINUTES` | `480` | No | Token TTL in minutes |
| `DEMO_USERS` | (JSON with admin/acme/globex) | No | Override demo user credentials |
| `PYTHON_VERSION` | _(from runtime.txt)_ | Yes | Must be `3.11.10` on Render |
| `VITE_API_URL` | _(frontend env)_ | Yes (prod) | Backend base URL for the React app |
