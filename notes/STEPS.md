# Build Order (Step-by-Step)

Each step must verify before continuing. This file is the running log.

| Step | Module | Status | Verification |
|---|---|---|---|
| 1 | Architecture + folder structure | ✅ | `docs/ARCHITECTURE.md` reviewed |
| 2 | Backend foundation (FastAPI, config, logging, /health) | ✅ | `uvicorn app.main:app` boots; `/api/v1/health` returns 200 |
| 3 | Data ingestion pipeline (loader → cleaner → aggregator → templater) | ✅ | `POST /api/v1/ingest` returns chunk counts; sandbox-verified |
| 4 | Embeddings + ChromaDB | ✅ | `POST /api/v1/embed` upserts vectors; `GET /api/v1/embed/status` shows count |
| 5 | Hybrid search (BM25 + semantic + RRF) | ✅ | `GET /api/v1/incidents?q=...` returns ranked results |
| 6 | RAG pipeline (prompts + LLM + JSON schema) | ✅ | `POST /api/v1/analyze` returns answer + causes + recs (template fallback works without API key) |
| 7 | Multi-agent system (4 agents + orchestrator) | ✅ | Each agent's output visible in `agent_trace`; sandbox-verified |
| 8 | Telemetry analytics + dataset ETL endpoints | ✅ | `/grid-score`, `/heatmap`, `/timeline`, `/telemetry`, `/recommendations`, `/datasets/*` |
| 9 | Frontend foundation (Vite + Tailwind + routing) | — | `npm run dev` shows sidebar + pages |
| 10 | Premium UI (glassmorphism, animations, theme) | — | Visual review |
| 11 | Dashboard visuals (charts, gauges, heatmaps) | ✅ | HealthGauge, RegionBars, TelemetryLineChart, TimelineArea, SeverityPie, HeatmapGrid, AgentFlow built |
| 12 | Frontend ↔ backend integration | ✅ | All 12 pages live; cross-page navigation, useApi polling hook, click-to-filter |
| 13 | Real-time WebSocket telemetry | — | Live chart updates |
| 14 | DeepEval + LLM-as-judge | — | Eval scores attached to `/analyze` response |
| 15 | Render deployment | ✅ | `render.yaml` finalized (backend + frontend + persistent disk); `docs/DEPLOYMENT.md` walkthrough |
| 16 | Documentation pack (README, FLOW, QA, PRESENTATION) | ✅ | Top README · `PROJECT_FLOW.md` · `PANEL_QA.md` · `PRESENTATION_GUIDE.md` · `DEPLOYMENT.md` |

## Cross-cutting enhancements

| Enhancement | Status | Where |
|---|---|---|
| Input guardrails (PII block/mask + topic restriction) | ✅ Built | `backend/app/utils/guardrails.py`, `POST /api/v1/guardrails/validate-query` |
| Multi-tenancy + JWT auth | ✅ Built | `core/auth.py`, `core/security.py`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`. Off by default (MULTI_TENANCY_ENABLED=false). Demo users: admin/admin, acme/acme123, globex/globex123. |
| LLM offline fallback | ✅ Built | `rag/llm.py` `TemplateProvider` — `/analyze` always returns structured response even without API keys. |

## Scope decisions

- **No login page** (2026-05-29). Replaced with an Operator identifier field
  in the sidebar + audit-log middleware. The objective does not demand per-user
  authentication, and a single shared dashboard fits a homogeneous engineer
  user-class better. JWT + multi-tenancy can be added later without re-ingest
  thanks to the `tenant_id` metadata slot already on every chunk.
- **Name + street-address NOT masked** by guardrails — operators legitimately
  reference them. Email / phone / IP / SSN / credit-card / passport / API-key
  still handled.

## Dashboard interactions (decided)

- **"Refresh Data" button** → `POST /api/v1/ingest` then `POST /api/v1/embed`.
- **"Run Full Analysis" button** → fan-out to `/grid-score`, `/heatmap`,
  `/timeline`, `/recommendations`.
- **Region heatmap** → click a region tile → filter the incident list and
  charts to that region (`?region=South+Zone`).
- **Top Critical Issues** → sorted bar chart of incidents by severity score;
  click to open the incident's evidence card.

## Notes log

- 2026-05-29: STEP 1 + 2 generated. Python 3.13 detected on the local machine; `requirements.txt` split into core + `requirements-ml.txt` so STEP 2 installs cleanly without the heavy ML stack. Render pinned to Python 3.11.10 via `runtime.txt`.
- 2026-05-29: Dataset sources confirmed and documented in `datasets/README.md`:
  - Primary: Kaggle — Smart Grid Stability (`smart_grid_stability_augmented.csv`)
  - Alt 1: UCI — Individual Household Electric Power Consumption
  - Alt 2: Kaggle — Electric Power Consumption Data Set
  All three are read by the ingestion pipeline in STEP 3 and normalized to a common schema.
