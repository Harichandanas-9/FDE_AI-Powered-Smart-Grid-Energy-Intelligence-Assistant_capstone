# Run From Scratch — VS Code Guide (Windows)

This runs the Smart Grid AI Assistant end-to-end on a fresh machine. Two terminals: one for the backend, one for the frontend. **No ETL click is required** — data loads automatically at startup.

## Prerequisites (install once)
- **Python 3.11** (matches `runtime.txt`) — https://www.python.org/downloads/release/python-31110/ (tick "Add to PATH")
- **Node.js 18+** (LTS) — https://nodejs.org
- **VS Code** with the Python extension.

Open the project folder in VS Code:
`File → Open Folder →` `C:\Users\harichandana.p.PRODAPT\Documents\capstone\AFDE_AI-Powered-Smart-Grid-Energy-Intelligence-Assistant_capstone`

---

## Terminal 1 — Backend (FastAPI on :8000)

Open a terminal: `` Terminal → New Terminal `` (PowerShell). Then:

```powershell
cd backend

# 1. Create a fresh virtual environment (Python 3.11)
py -3.11 -m venv venv

# 2. Activate it
venv\Scripts\Activate.ps1
# If PowerShell blocks the script, run this once then re-activate:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. Install dependencies (now includes chromadb + rank-bm25)
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Make sure .env exists (copy the template if not)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 5. Start the API
uvicorn app.main:app --port 8000
```

Backend is ready when you see `startup_complete`. Verify:
- Health: http://localhost:8000/api/v1/health  → `"status":"ok"`
- API docs: http://localhost:8000/docs

> The app auto-ingests `datasets/smart_grid_stability_augmented.csv` at startup if no processed data exists, so every tab has data immediately. Keep `EMBEDDING_MODEL=hash` in `.env` for a fast, dependency-free demo. To use a real LLM, set `OPENAI_API_KEY=sk-...` in `.env` (optional — a deterministic template answer works without it).

---

## Terminal 2 — Frontend (Vite on :5173)

Open a **second** terminal (the split icon, or `Terminal → New Terminal`):

```powershell
cd frontend

# 1. Install dependencies (first run only)
npm install

# 2. Start the dev server
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api → http://localhost:8000`, so no extra config is needed.

---

## What you should see (demo checklist)
| Tab | Shows immediately |
|---|---|
| Dashboard | grid health score, region bars, heatmap, timeline, recent recommendations |
| Query Console / Chat | type a question → answer + evidence + root causes + recommendations + confidence |
| ETL | the loaded `smart_grid_stability_augmented.csv`, schema/source, ETL run history, upload button |
| Incident Intelligence | incident results (hybrid search + browse) |
| Telemetry Analytics | telemetry samples, voltage/load/stability patterns, anomaly correlations |
| Grid Stability / Failure / Agents | stability scores, failure analysis, multi-agent trace |

## Quick smoke test (optional, Terminal 1 with venv active)
```powershell
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/incidents?q=transformer overload"
curl http://localhost:8000/api/v1/grid-score
```

---

## Troubleshooting
- **Frontend blank page** → check Terminal 2 for a red Vite compile error; it names the file/line. (The previously-corrupted `Dashboard.jsx` is now fixed.)
- **`uvicorn` not found** → the venv isn't active; re-run `venv\Scripts\Activate.ps1`.
- **Port already in use** → `uvicorn app.main:app --port 8001` (and set `VITE_API_URL=http://localhost:8001` in `frontend/.env`), or close the other process.
- **ETL "Process" button** → now completes in ~1–2 s and never hard-fails. If ChromaDB can't initialize on this machine, ETL still succeeds (`chroma_status: skipped`) because search/dashboard/chat run on the BM25 + JSONL backbone.
- **PowerShell won't activate venv** → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## To stop
Press `Ctrl+C` in each terminal.
