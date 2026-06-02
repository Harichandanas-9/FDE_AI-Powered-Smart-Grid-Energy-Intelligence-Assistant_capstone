# AI-Powered Smart Grid Energy Intelligence Assistant

> **Capstone Project** — Full-stack RAG + Multi-Agent intelligence platform
> that lets utility engineers investigate grid incidents in natural language.

![status](https://img.shields.io/badge/build-complete-success) ![python](https://img.shields.io/badge/python-3.11%2B-blue) ![react](https://img.shields.io/badge/react-18-61dafb)

---

## What it does

Operators type a question in plain English — *"Voltage instability in South
Zone during evening peak — what are the likely causes?"* — and get:

- **Grounded answer** with cited evidence chunks
- **Root causes** with probabilities + the historical incidents that drove them
- **Mitigation recommendations** with priority levels and rationale
- **Grid Health Score** (0–100) computed deterministically
- **Multi-agent trace** showing which stage contributed what
- **Evaluation scores** (faithfulness, LLM-judge accuracy, format correctness)
- **One-click PDF report** of the entire analysis

All over a glassmorphism dashboard with per-page accents, animated charts, and
a live WebSocket telemetry mode.

---

## Tech stack

| Layer | Stack |
|---|---|
| **Backend** | Python 3.11 · FastAPI · Uvicorn · pydantic-settings |
| **AI / RAG** | LangChain · ChromaDB · sentence-transformers (MiniLM) · BM25 · Reciprocal Rank Fusion |
| **Multi-agent** | 4 agents (Retrieval, Stability, Failure, Recommendation) + sequential orchestrator |
| **Evaluation** | DeepEval · LLM-as-judge · deterministic heuristic metrics (always-on fallback) |
| **Frontend** | React 18 · Vite · Tailwind CSS · Framer Motion · Recharts · Lucide icons |
| **Realtime** | FastAPI WebSocket simulator |
| **Auth** | JWT (PyJWT) · multi-tenant ready (off by default) |
| **Reporting** | reportlab PDF export |
| **Deploy** | Render (`render.yaml` — backend web + static frontend + 1 GB persistent disk) |

---

## Build status — all 16 steps complete

| # | Module | Where it lives |
|---|---|---|
| 1 | Architecture + folder structure | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 2 | Backend foundation (FastAPI + `/health`) | `backend/app/main.py` |
| 3 | Data ingestion pipeline | `backend/app/data/*` |
| 4 | Embeddings + ChromaDB | `backend/app/rag/embeddings.py`, `vector_store.py` |
| 5 | Hybrid search (BM25 + semantic + RRF) | `backend/app/rag/hybrid_retriever.py` |
| 6 | RAG pipeline + `/analyze` | `backend/app/rag/rag_pipeline.py` |
| 7 | Multi-agent orchestrator | `backend/app/agents/*` |
| 8 | Analytics + dataset ETL endpoints | `backend/app/services/`, `api/routes_analytics.py`, `api/routes_datasets.py` |
| 9 | Frontend foundation (Vite + Tailwind) | `frontend/src/` |
| 10 | Premium UI (glass, animations) | `frontend/src/components/`, `pages/Dashboard.jsx`, `pages/ETL.jsx` |
| 11 | Dashboard visuals (charts, gauges, heatmaps) | `frontend/src/components/charts/*` |
| 12 | Frontend ↔ backend integration | all 12 pages live |
| 13 | Real-time WebSocket telemetry + PDF export | `routes_ws.py`, `routes_pdf.py`, `useWebSocket.js` |
| 14 | DeepEval + LLM-as-judge + heuristic | `backend/app/evaluation/*`, `EvalBadges.jsx` |
| 15 | Render deployment | [`render.yaml`](render.yaml), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) |
| 16 | Documentation pack | [`docs/`](docs/) |

Also delivered as cross-cutting concerns:

- **Input guardrails** (PII block/mask + topic restriction) — `backend/app/utils/guardrails.py`
- **Multi-tenancy + JWT** — off by default; flip `MULTI_TENANCY_ENABLED=true` to enable
- **LLM offline fallback** — `TemplateProvider` keeps `/analyze` working without any API key

---

## Quick start (local — Windows / VS Code)

```powershell
# Open the project in VS Code: File -> Open Folder -> this folder.
# All commands below run from terminals inside VS Code (Ctrl + `).

# ───── 1. BACKEND (terminal 1) ─────
cd backend
py -3.11 -m venv venv                  # or: python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt        # core deps (~30 s)
pip install -r requirements-ml.txt     # ML stack (~5 min first time)
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# ───── 2. FRONTEND (terminal 2) ─────
cd frontend
npm install                            # first time only (~1 min)
npm run dev

# Open in browser:
#   Frontend dashboard: http://localhost:5173/
#   Backend Swagger UI: http://localhost:8000/docs
#   Backend health:     http://localhost:8000/api/v1/health
```

Then in the UI:
1. Go to the **ETL** tab → upload the CSVs (links in [`datasets/README.md`](datasets/README.md))
2. Click **Run ETL** on each row
3. Return to **Dashboard** → see KPIs, gauge, region health, heatmap, timeline populate
4. Click **Query Console** → ask questions in plain English

---

## API surface

| Endpoint | Purpose |
|---|---|
| `GET  /api/v1/health` | Liveness + component status |
| `POST /api/v1/auth/login` | Issue JWT (form-encoded) |
| `GET  /api/v1/auth/me` | Current principal |
| `POST /api/v1/guardrails/validate-query` | Test guardrails on a string |
| `POST /api/v1/ingest` | Run ingestion across all CSVs |
| `POST /api/v1/embed` | Embed `chunks.jsonl` into Chroma |
| `GET  /api/v1/datasets` | List CSVs in `datasets/` |
| `POST /api/v1/datasets/upload` | Upload a CSV (multipart) |
| `POST /api/v1/datasets/{filename}/process` | **Run ETL** on one file (ingest + embed) |
| `DELETE /api/v1/datasets/{filename}` | Delete a CSV |
| `GET  /api/v1/incidents` | Hybrid search + metadata filter |
| `POST /api/v1/analyze` | **Headline endpoint** — multi-agent response |
| `GET  /api/v1/grid-score` | Overall + per-region health |
| `GET  /api/v1/heatmap` | Region × severity matrix |
| `GET  /api/v1/timeline` | Severity-stacked over time |
| `GET  /api/v1/telemetry` | Recent telemetry samples |
| `GET  /api/v1/recommendations` | Last cached /analyze responses |
| `POST /api/v1/evaluate` | DeepEval + LLM-judge + heuristic |
| `POST /api/v1/export/pdf` | Download analyze response as PDF |
| `WS   /api/v1/ws/telemetry` | Live telemetry stream |

Full schemas at `http://localhost:8000/docs`.

---

## Documentation map

| Doc | Audience |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design — diagrams, decisions, trade-offs |
| [`docs/PROJECT_FLOW.md`](docs/PROJECT_FLOW.md) | Per-file responsibilities + request flow |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Render deployment walkthrough |
| [`docs/PRESENTATION_GUIDE.md`](docs/PRESENTATION_GUIDE.md) | 10-minute panel demo runbook |
| [`docs/PANEL_QA.md`](docs/PANEL_QA.md) | 20 likely panel questions + answers |
| [`backend/README.md`](backend/README.md) | Backend run + test |
| [`frontend/README.md`](frontend/README.md) | Frontend run + theme |
| [`datasets/README.md`](datasets/README.md) | Where to download the CSVs |
| [`notes/STEPS.md`](notes/STEPS.md) | Running log of build status + decisions |

---

## Smoke tests (run from project root)

```powershell
python scripts\smoke_test_backend.py        # boots app in-process, hits /health
python scripts\smoke_test_guardrails.py     # 13 test queries through guardrails
python scripts\smoke_test_ingestion.py      # CSV -> chunks.jsonl
python scripts\smoke_test_embeddings.py     # chunks.jsonl -> Chroma
python scripts\smoke_test_search.py         # hybrid retrieve
python scripts\smoke_test_analyze.py        # full /analyze pipeline (template fallback)
python scripts\smoke_test_orchestrator.py   # multi-agent flow
python scripts\smoke_test_analytics.py      # grid-score, heatmap, timeline
python scripts\smoke_test_auth.py           # JWT round-trip + multi-tenancy
python scripts\smoke_test_stream.py         # telemetry simulator
python scripts\smoke_test_eval.py           # DeepEval + LLM-judge + heuristic
```

All run independently of the server. Pass = `[smoke] OK ✓` at the end.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: pydantic_settings` | `pip install -r requirements.txt` didn't complete — re-run it |
| `chromadb` install fails | Ensure Python 3.11 (`runtime.txt` pins this on Render) |
| Sentence-transformers slow on first call | Normal — model downloads ~80 MB once, then cached |
| Frontend can't reach backend | Make sure backend is on `:8000` and frontend proxy in `vite.config.js` points at it |
| CORS error in browser | Add the frontend origin to `CORS_ORIGINS` in `.env` |
| Empty dashboard | Run ETL once: upload CSVs → click "Run ETL" |
| Off-topic queries get refused | Working as intended — see [`docs/PANEL_QA.md`](docs/PANEL_QA.md) Q11 |

---

## License & attribution

Datasets used (per capstone requirements):
- [Kaggle — Smart Grid Stability](https://www.kaggle.com/datasets/pcbreviglieri/smart-grid-stability)
- [UCI — Individual Household Electric Power Consumption](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption)
- [Kaggle — Electric Power Consumption](https://www.kaggle.com/datasets/uciml/electric-power-consumption-data-set)

Project structure, AI pipeline, and UI built for capstone evaluation purposes.
