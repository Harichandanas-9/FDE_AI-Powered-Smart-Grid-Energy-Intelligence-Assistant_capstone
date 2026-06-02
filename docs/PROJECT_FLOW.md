# Project Flow — File Responsibilities & Execution

Complete map of every file, what it does, and how requests travel through the system.

---

## Entry Points

| Entry point | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app factory — uvicorn loads this |
| `frontend/src/main.jsx` → `App.jsx` | React router — Vite loads this |
| `render.yaml` | Both services + persistent disk for production |

---

## Backend Folder Structure

```
backend/
├── requirements.txt              Core deps: FastAPI, Pydantic, JWT, ReportLab, WebSockets
├── requirements-ml.txt           ML deps: ChromaDB, sentence-transformers, rank-bm25, DeepEval
├── runtime.txt                   Pins Render to Python 3.11.10
├── .env.example                  Template for local .env file
└── app/
    ├── __init__.py               Exports __version__
    ├── main.py                   FastAPI factory: CORS, request-id middleware, all routers
    │
    ├── core/
    │   ├── config.py             pydantic-settings Settings class — single source of truth
    │   │                         for all env vars; @lru_cache singleton via get_settings()
    │   ├── logging.py            Structured JSON logger (python-json-logger)
    │   ├── lifespan.py           Async startup hook: loads BM25 index, records component
    │   │                         health status dict on app.state.components
    │   ├── auth.py               JWT encode/decode (PyJWT HS256) + demo user store
    │   │                         parsed from DEMO_USERS env var
    │   └── security.py           FastAPI dependency get_current_principal():
    │                             returns synthetic principal when multi-tenancy disabled,
    │                             validates Bearer JWT otherwise
    │
    ├── api/                      One file per endpoint group
    │   ├── routes_health.py      GET  /health — liveness + component status dict
    │   │                         GET  /       — root banner
    │   ├── routes_auth.py        POST /auth/login — returns JWT
    │   │                         GET  /auth/me   — returns principal from token
    │   ├── routes_validate.py    POST /guardrails/validate-query
    │   │                         Runs guardrails without a full analyze call
    │   ├── routes_ingest.py      POST /ingest — runs CSV → chunks.jsonl pipeline
    │   │                         GET  /ingest/status — last report + ChromaDB fallback
    │   ├── routes_embed.py       POST /embed — embeds chunks.jsonl → ChromaDB
    │   ├── routes_datasets.py    GET  /datasets       — list processed datasets
    │   │                         POST /datasets/{name}/process — ETL + embed in one call
    │   │                         DELETE /datasets/{name}      — remove from ChromaDB
    │   ├── routes_incidents.py   GET  /incidents?q=&region=&severity=&source=
    │   │                         Full-text + metadata search with pagination
    │   ├── routes_analyze.py     POST /analyze — headline endpoint
    │   │                         Runs AgentOrchestrator; caches result for /recommendations
    │   ├── routes_analytics.py   GET  /grid-score       — overall + per-region health
    │   │                         GET  /heatmap          — region x severity matrix
    │   │                         GET  /timeline?bucket= — chronological incidents
    │   │                         GET  /telemetry        — recent telemetry summary
    │   │                         GET  /recommendations  — cached recent /analyze responses
    │   ├── routes_eval.py        POST /evaluate — DeepEval + LLM-as-judge scoring
    │   ├── routes_predict.py     GET  /predict — deterministic per-region risk prediction
    │   ├── routes_pdf.py         POST /export/pdf — ReportLab PDF of analyze result
    │   └── routes_ws.py          WS   /ws/telemetry — live telemetry stream
    │
    ├── models/
    │   └── schemas.py            ALL Pydantic request + response models:
    │                             AnalyzeRequest, AnalyzeResponse, IngestRequest,
    │                             IngestResponse, EvalRequest, EvalResponse, etc.
    │
    ├── data/                     ETL pipeline (STEP 3)
    │   ├── loader.py             CSV reading with auto-delimiter detection + chunked IO
    │   ├── normalizer.py         Maps each CSV schema to common 12-field grid schema:
    │   │                         timestamp, voltage, frequency, stability_index,
    │   │                         demand, region, severity, equipment_type, etc.
    │   ├── cleaner.py            Drops NaN rows, clips outliers to IQR bounds
    │   ├── aggregator.py         Groups raw readings into hourly incident windows;
    │   │                         computes mean/std/max per field; tags outage_event
    │   ├── templater.py          Converts an aggregated row to a natural-language
    │   │                         narrative string for embedding + a chunk dict with metadata
    │   └── ingestion_pipeline.py End-to-end orchestrator: loader → normalizer → cleaner
    │                             → aggregator → templater → writes data_processed/chunks.jsonl
    │                             Returns IngestionReport with per-source stats
    │
    ├── rag/                      Vector store + retrieval (STEPs 4-6)
    │   ├── embeddings.py         Sentence-transformers wrapper with HashEmbedder fallback.
    │   │                         get_embedder() returns cached model; embed_texts() and
    │   │                         embed_query() are public entry points.
    │   ├── vector_store.py       ChromaDB persistent client: get_client(),
    │   │                         get_or_create_collection(), upsert_chunks(), query_collection()
    │   ├── bm25_index.py         rank-bm25 keyword index. BM25Index.build(corpus),
    │   │                         BM25Index.search(query, top_k), save/load pkl
    │   ├── hybrid_retriever.py   HybridRetriever.retrieve(): semantic (Chroma) + keyword (BM25)
    │   │                         fused via Reciprocal Rank Fusion → List[RetrievedChunk]
    │   │                         Tenant-aware: $or filter for [caller_tenant, "default"]
    │   ├── reranker.py           Optional cross-encoder reranking. Only runs when
    │   │                         RERANKER_ENABLED=true. Uses ms-marco-MiniLM-L-6-v2.
    │   ├── prompt_templates.py   System prompt + user prompt + JSON schema contract.
    │   │                         format_context(chunks) compresses retrieved text.
    │   ├── llm.py                get_provider(settings) returns OpenAI / Anthropic /
    │   │                         Ollama / TemplateProvider based on LLM_PROVIDER env var
    │   └── rag_pipeline.py       Direct RAG pipeline (without full agent orchestrator):
    │                             guardrails → retrieve → format prompt → LLM → validate JSON
    │
    ├── agents/                   Multi-agent system (STEP 7)
    │   ├── base_agent.py         BaseAgent ABC: execute() wraps run() with timing, error
    │   │                         handling, agent_trace update. Each agent has name property.
    │   ├── retrieval_agent.py    RetrievalAgent: calls HybridRetriever.retrieve() and
    │   │                         writes results to envelope["retrieved"]
    │   ├── stability_agent.py    StabilityAgent: reads envelope["retrieved"] chunks,
    │   │                         computes Grid Health Score 0-100 (voltage 30%, frequency 20%,
    │   │                         stability index 50%), writes envelope["stability_analysis"]
    │   ├── failure_agent.py      FailureAgent: rule-based pattern matching on retrieved
    │   │                         chunks and stability analysis; writes envelope["root_causes"]
    │   │                         as [{cause, probability, evidence_ids}]
    │   ├── recommendation_agent.py  RecommendationAgent: formats prompt from envelope context,
    │   │                            calls LLM provider, validates JSON schema, writes
    │   │                            envelope["recommendations"], ["answer"], ["confidence"]
    │   └── orchestrator.py       AgentOrchestrator.run(): initialises envelope dict,
    │                             runs guardrails, then executes agents sequentially.
    │                             Shared envelope is mutated by each agent in order.
    │
    ├── services/
    │   ├── analytics_service.py  Aggregations for dashboard widgets: grid_health_score(),
    │   │                         heatmap_data(), timeline_data(), telemetry_summary(),
    │   │                         recent_recommendations(), record_recommendation().
    │   │                         _fetch_all() used by routes_predict as data source.
    │   └── stream_service.py     WebSocket telemetry generator: stream_telemetry(mode)
    │                             replays chunks.jsonl rows at 1/rate seconds; if no file,
    │                             synthesises sinusoidal voltage/frequency ticks
    │
    ├── evaluation/
    │   ├── metrics.py            Heuristic evaluation: faithfulness (chunk overlap),
    │   │                         answer coverage (keyword overlap), format compliance
    │   ├── llm_judge.py          LLM-as-judge: accuracy, completeness, actionability scores
    │   │                         with heuristic fallback when LLM unavailable
    │   └── deepeval_runner.py    DeepEval wrapper: Faithfulness, AnswerRelevancy,
    │                             ContextualRecall metrics with heuristic fallback
    │
    └── utils/
        └── guardrails.py         validate_query() → GuardrailVerdict.
                                  Layer 1: BLOCK PII (SSN, credit card, API keys) → refuse.
                                  Layer 2: MASK PII (email, phone, IP) → continue.
                                  Layer 3: Topic check against DOMAIN_KEYWORDS → refuse if off-topic.
```

---

## Frontend Folder Structure

```
frontend/
├── package.json                  React 18.3 + Vite 5.4 + Tailwind 3.4 + Framer Motion 11
│                                 + Recharts 2.13 + Lucide React + Axios + React Router 6
├── vite.config.js                /api/* proxy → :8000 (dev only); React plugin
├── tailwind.config.js            Per-page accent palette + glass token extensions
├── postcss.config.js             Tailwind + autoprefixer PostCSS pipeline
├── index.html                    Fonts (system stack), root div, Vite entry
└── src/
    ├── main.jsx                  React 18 createRoot mount
    ├── App.jsx                   BrowserRouter + 13 Routes (one per page)
    │
    ├── services/
    │   └── api.js                Axios instance with VITE_API_URL base URL.
    │                             Exports named wrappers for all 18 endpoints:
    │                             Analyze(), Ingest(), Embed(), GridScore(), Heatmap(),
    │                             Timeline(), Telemetry(), Recommendations(), Incidents(),
    │                             Evaluate(), Predict(), ExportPdf(), Login(), GetMe(),
    │                             ValidateQuery(), Datasets(), EtlLastRun(), ClearEtlCache()
    │
    ├── hooks/
    │   ├── useApi.js             Generic async hook: { data, loading, error, refetch }.
    │   │                         Supports polling interval for live-updating widgets.
    │   └── useWebSocket.js       Auto-reconnecting WebSocket client.
    │                             Maintains messages[] ring buffer; exposes isConnected flag.
    │
    ├── styles/
    │   └── index.css             Tailwind base/components/utilities.
    │                             Component layer: .glass, .pill, .surface, .text-accent
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx     Outer shell: Sidebar + Topbar + <Outlet /> (React Router)
    │   │   ├── Sidebar.jsx       Navigation links for all 13 pages with active state
    │   │   └── Topbar.jsx        App title, connection status, user info
    │   │
    │   ├── cards/
    │   │   ├── GlassCard.jsx     Base glassmorphism card with backdrop-blur + border
    │   │   ├── MetricCard.jsx    KPI tile: label + large value + delta indicator
    │   │   ├── LoadingDots.jsx   Animated three-dot loading indicator
    │   │   └── EvalBadges.jsx    Renders DeepEval + LLM-judge scores as colour-coded pills
    │   │
    │   └── charts/
    │       ├── HealthGauge.jsx       SVG arc gauge 0-100 for overall grid health score
    │       ├── RegionBars.jsx        Horizontal bar chart of per-region incident counts
    │       ├── SeverityPie.jsx       Donut chart of incidents by severity level
    │       ├── TelemetryLineChart.jsx  Multi-series Recharts LineChart for voltage/frequency
    │       ├── TimelineArea.jsx      Stacked AreaChart of incidents per time bucket
    │       ├── HeatmapGrid.jsx       Custom SVG grid: rows = regions, cols = severities,
    │       │                         fill opacity proportional to incident count
    │       └── AgentFlow.jsx         SVG pipeline diagram of agents with timing bars
    │                                 and status colour coding
    │
    └── pages/
        ├── Dashboard.jsx          Home page: loads grid-score + heatmap + timeline +
        │                          recommendations in Promise.all; renders KPI cards,
        │                          HealthGauge, RegionBars, HeatmapGrid, TimelineArea,
        │                          ETL status banner, predictive alerts
        ├── QueryConsole.jsx        Natural-language query input; calls /analyze; renders
        │                          chat bubble, agent_trace strip, root cause cards,
        │                          evidence list, eval badges
        ├── ETL.jsx                 Dataset list; Run ETL + Embed buttons; progress display;
        │                          cache-busting ETL status polling
        ├── GridStability.jsx       Calls /grid-score; displays stability score gauge,
        │                          per-region voltage and frequency stats
        ├── FailureAnalysis.jsx     Calls /incidents + /analyze; displays root cause cards
        │                          with probability bars and evidence references
        ├── SmartMeter.jsx          Calls /incidents?source=household_power; applies
        │                          threshold anomaly classification; renders badges,
        │                          expandable detail panels, trend chart
        ├── Telemetry.jsx           WebSocket live feed via useWebSocket hook;
        │                          TelemetryLineChart scrolling in real time
        ├── Recommendations.jsx     Calls /recommendations; displays cached /analyze
        │                          responses with summaries and action steps
        ├── AgentVisualization.jsx  Query input + AgentFlow chart + per-agent output panels;
        │                          shows evidence chunks, similarity scores, timing bars
        ├── IncidentTimeline.jsx    Calls /timeline; renders TimelineArea with bucket toggle
        ├── HeatmapAnalytics.jsx    Calls /heatmap; renders full HeatmapGrid with filters
        ├── Settings.jsx            API URL, tenant ID, LLM model display; saves to localStorage
        ├── PredictiveIntelligence.jsx  Calls /predict; renders per-region risk cards,
        │                              global alerts, recommended actions
        └── Placeholder.jsx         Fallback for unimplemented routes (404 style)
```

---

## Request Flow — POST /analyze (Headline Endpoint)

```
1. React: QueryConsole.jsx
      user submits query text (+ optional region/severity filters)
         |
         v
2. api.js: Analyze({ query, region, severity, top_k })
      axios POST /api/v1/analyze
      Header: Authorization: Bearer <jwt> (when multi-tenancy enabled)
         |
         v
3. FastAPI: routes_analyze.py → analyze()
      extracts principal (tenant_id, username) via get_current_principal()
      builds filters dict from req.region / req.severity / req.source
         |
         v
4. AgentOrchestrator.run(query, tenant_id, filters)
      initialises envelope dict with query, tenant_id, filters
         |
         |-- Guardrails: guardrails.validate_query(query)
         |       block SSN/credit-card/API-key → refuse with message
         |       mask email/phone/IP → continue with masked_query
         |       topic check vs DOMAIN_KEYWORDS → refuse if off-topic
         |       writes envelope["guardrail"] + ["agent_trace"][0]
         |
         |-- RetrievalAgent.run(envelope)
         |       HybridRetriever.retrieve(masked_query, top_k, where=filters, tenant_id)
         |         → embed_query(masked_query)          [384-dim MiniLM or hash]
         |         → query_collection(chroma, embedding, top_k=20, where)
         |         → bm25_index.search(masked_query, top_k=20)
         |         → RRF fusion (semantic w=0.6, keyword w=0.4, k=60)
         |         → returns List[RetrievedChunk] sorted by fused score
         |       writes envelope["retrieved"]
         |       appends agent_trace entry with timing_ms + summary
         |
         |-- StabilityAgent.run(envelope)
         |       reads envelope["retrieved"] chunks
         |       extracts voltage_mean, frequency_mean, stability_score_mean
         |       computes Grid Health Score: voltage 30% + frequency 20% + stability 50%
         |       classifies: healthy >=70, warning 40-70, critical <40
         |       writes envelope["stability_analysis"]
         |       appends agent_trace entry
         |
         |-- FailureAgent.run(envelope)
         |       rule-based pattern matching on stability_analysis + retrieved chunks
         |       identifies root causes: voltage_deviation, frequency_instability,
         |         transformer_overload, high_demand, outage_pattern, etc.
         |       assigns probability (0-1) + evidence chunk IDs per cause
         |       writes envelope["root_causes"]
         |       appends agent_trace entry
         |
         |-- RecommendationAgent.run(envelope)
         |       formats prompt: system prompt + root causes + retrieved context + query
         |       calls LLM provider (OpenAI / Anthropic / TemplateProvider)
         |       validates JSON schema response
         |       writes envelope["recommendations"], ["answer"], ["confidence"], ["reasoning"]
         |       appends agent_trace entry
         |
         v
5. routes_analyze.py
      analytics_service.record_recommendation(envelope) → caches for /recommendations
      returns AnalyzeResponse (Pydantic-serialised envelope)
         |
         v
6. React: QueryConsole.jsx renders
      chat bubble with envelope["answer"]
      agent_trace strip (AgentFlow component with timing)
      root cause cards from envelope["root_causes"]
      evidence list from envelope["retrieved"]
      EvalBadges component (triggers separate /evaluate call if eval enabled)
```

---

## Request Flow — ETL + Embed (Dataset Ingestion)

```
1. React: ETL.jsx
      user clicks "Run ETL" for a dataset
         |
         v
2. api.js: Ingest({ sources: [source_key] })
      POST /api/v1/ingest
         |
         v
3. routes_ingest.py → ingest()
      run_ingestion(sources, max_rows_override)
         |
         |-- data/loader.py:        read CSV (auto-delimiter, chunked)
         |-- data/normalizer.py:    map columns to 12-field common schema
         |-- data/cleaner.py:       drop NaN, clip outliers
         |-- data/aggregator.py:    group into hourly windows
         |-- data/templater.py:     row → narrative string + metadata dict
         |-- write data_processed/chunks.jsonl
         |
         v
      returns IngestResponse { chunks_written, per_source, duration_seconds }
      updates app.state.components["ingestion"] = "ok"
         |
         v
4. React: ETL.jsx calls Embed() on success
      POST /api/v1/embed
         |
         v
5. routes_embed.py → embed()
      reads data_processed/chunks.jsonl
      embed_texts(chunk_texts) → (N, 384) float32 array
      upsert_chunks(chroma_collection, chunks, embeddings, tenant_id)
      rebuilds BM25 index from chunks corpus
      saves bm25_index.pkl
         |
         v
      returns { vectors_upserted, duration_seconds }
         |
         v
6. React: ETL.jsx
      shows success toast
      calls ClearEtlCache() to invalidate stale status
      refreshes dataset list
```

---

## Request Flow — Dashboard Load

```
React: Dashboard.jsx useEffect load()
   |
   |-- Promise.all([
   |     GET /api/v1/grid-score,          → overall_score + per_region health
   |     GET /api/v1/heatmap,             → regions x severities incident matrix
   |     GET /api/v1/timeline?bucket=day, → daily incident buckets
   |     GET /api/v1/recommendations,     → last 5 /analyze cached responses
   |     GET /api/v1/ingest/status,       → ETL last run timestamp
   |     GET /api/v1/predict,             → per-region risk scores + global alerts
   |   ])
   |
   v
All resolve → setState for each widget
   |
   |-- HealthGauge(overall_score)
   |-- MetricCards(n_incidents, avg_health, critical_count, regions)
   |-- RegionBars(per_region health scores)
   |-- HeatmapGrid(heatmap matrix)
   |-- TimelineArea(timeline series)
   |-- ETL status banner (etlEffectivelyRan logic)
   |-- Global alerts from /predict (top 3 risks)
   |-- RecentRecs list from /recommendations
   v
Dashboard fully rendered
```

---

## Request Flow — WebSocket Telemetry

```
React: Telemetry.jsx — user enables Live toggle
   |
   v
useWebSocket('/api/v1/ws/telemetry?mode=auto&rate=2')
   |
   v
routes_ws.py: ws_telemetry(websocket, mode, rate, token)
   |
   |-- JWT check (only when MULTI_TENANCY_ENABLED=true)
   |
   |-- stream_service.stream_telemetry(mode='auto', rate=2)
   |     if data_processed/chunks.jsonl exists:
   |       replay rows in order, one tick per (1/rate) seconds
   |       each tick: {timestamp, voltage, frequency, stability_index, demand, region}
   |     else:
   |       synthesise sinusoidal voltage (~230V +/- noise) + frequency (~50Hz +/- drift)
   |
   v
ws.send_text(JSON tick) every 0.5 s
   |
   v
React useWebSocket appends tick to messages[] ring buffer (max 200)
TelemetryLineChart re-renders with sliding window
```

---

## Request Flow — Predictive Intelligence

```
React: PredictiveIntelligence.jsx load()
   |
   v
api.js: Predict()
   GET /api/v1/predict
      Authorization: Bearer <jwt>
   |
   v
routes_predict.py → predict_failures(principal)
   |
   |-- analytics_service._fetch_all(tenant_id, max_rows=5000)
   |     queries ChromaDB collection for all chunks matching tenant filter
   |     returns List[{id, text, metadata}]
   |
   |-- group chunks by metadata["region"]
   |
   |-- for each region: _predict_region(chunks)
   |     extract voltage_mean, frequency_mean, stability_score_mean, demand_max
   |     compute: voltage_risk, freq_risk, stab_risk, outage_risk, overload_risk
   |     composite = 0.30*v + 0.20*f + 0.25*s + 0.15*o + 0.10*ovr
   |     assign risk_level: critical/high/medium/low
   |     build alerts[] and recommendations[] lists
   |
   |-- _predict_region(all_rows) → overall prediction
   |
   |-- global_alerts = regions with critical or high risk
   |
   v
returns { overall, per_region, global_alerts, highest_risk_region, n_incidents_analysed }
   |
   v
React: PredictiveIntelligence.jsx renders
   overall risk gauge
   per-region cards with risk score + alerts
   prioritised recommendations by category
```

---

## Data Flow — CSV to Query Response

```
CSV file (smart_grid_stability_augmented.csv)
   |
   v  [data/loader.py]
Raw DataFrame (semicolon or comma delimited, '?' → NaN)
   |
   v  [data/normalizer.py]
Normalised DataFrame (12 common fields: timestamp, voltage_mean, frequency_mean,
  stability_index, demand_kw, region, severity, equipment_type, source_dataset, etc.)
   |
   v  [data/cleaner.py]
Cleaned DataFrame (NaN dropped, outliers clipped to 1.5xIQR bounds)
   |
   v  [data/aggregator.py]
Aggregated Windows DataFrame (one row per hour per region:
  voltage_mean, voltage_std, frequency_mean, stability_score_mean,
  demand_max, outage_event, transformer_status)
   |
   v  [data/templater.py]
chunks.jsonl  (one JSON line per window)
  {
    "id": "chunk_<hash>",
    "text": "In North Zone at 14:00, voltage averaged 228.5V ...",
    "metadata": { "region": "North Zone", "severity": "high",
                  "voltage_mean": 228.5, "frequency_mean": 49.8,
                  "stability_score_mean": -0.12,
                  "transformer_status": "overload_risk",
                  "source_dataset": "smart_grid_stability",
                  "tenant_id": "default" }
  }
   |
   v  [rag/embeddings.py]
(N, 384) float32 array  (all-MiniLM-L6-v2 or HashEmbedder)
   |
   v  [rag/vector_store.py]
ChromaDB collection  ("smart_grid_incidents")
  Stored: id, embedding vector, document text, metadata dict
   |
   v  [rag/bm25_index.py]
BM25Index  (rank-bm25 over all chunk texts)
  Saved: data_processed/bm25_index.pkl
   |
   v  [rag/hybrid_retriever.py]  — at query time
  embed_query(q) → Chroma top-20 → semantic_ids
  bm25.search(q) → keyword top-20 → kw_ranked
  RRF fusion → fused_scores → top-5 RetrievedChunk objects
   |
   v  [agents/orchestrator.py]
Envelope with retrieved chunks → Stability → Failure → Recommendation agents → AnalyzeResponse
```

---

## Boot Sequence (Single uvicorn Process)

```
1. uvicorn loads app.main:app
2. configure_logging(level)           → JSON stdout handler
3. create_app()
     → registers all 17 API routers + CORS + request-id middleware
4. lifespan() startup:
     → Settings.from_env()
     → try load data_processed/bm25_index.pkl
         if absent: try build BM25 from chunks.jsonl
         if chunks.jsonl absent: bm25 = None (status: "no_chunks")
     → records component status dict:
         api, config, logging, ingestion, chroma, embeddings, bm25, llm, auth
5. Server starts listening on $PORT
6. First /analyze request (lazy):
     → HybridRetriever._collection() opens ChromaDB PersistentClient
     → get_embedder() loads SentenceTransformer model (~80 MB, CPU)
     → AgentOrchestrator instantiated with retriever + LLM provider
```

---

## API Endpoint Reference

| Method | Path | Auth Required | Description |
|---|---|---|---|
| GET | `/api/v1/health` | No | Liveness + component status |
| GET | `/` | No | Root banner |
| POST | `/api/v1/auth/login` | No | Returns JWT for username/password |
| GET | `/api/v1/auth/me` | Yes | Returns current principal |
| POST | `/api/v1/guardrails/validate-query` | No | PII + topic check only |
| POST | `/api/v1/ingest` | No | Run CSV → chunks.jsonl ETL |
| GET | `/api/v1/ingest/status` | No | Last ETL report |
| POST | `/api/v1/embed` | No | Embed chunks.jsonl → ChromaDB |
| GET | `/api/v1/datasets` | Yes | List processed datasets |
| POST | `/api/v1/datasets/{name}/process` | Yes | ETL + embed in one call |
| DELETE | `/api/v1/datasets/{name}` | Yes | Remove dataset from ChromaDB |
| GET | `/api/v1/incidents` | Yes | Search incidents with filters |
| POST | `/api/v1/analyze` | Yes | Multi-agent grid analysis |
| GET | `/api/v1/grid-score` | Yes | Overall + per-region health score |
| GET | `/api/v1/heatmap` | Yes | Region x severity matrix |
| GET | `/api/v1/timeline` | Yes | Chronological incident series |
| GET | `/api/v1/telemetry` | Yes | Recent telemetry summary |
| GET | `/api/v1/recommendations` | Yes | Cached recent /analyze results |
| POST | `/api/v1/evaluate` | Yes | DeepEval + LLM-judge scores |
| GET | `/api/v1/predict` | Yes | Per-region predictive risk |
| POST | `/api/v1/export/pdf` | Yes | PDF export of analysis |
| WS | `/api/v1/ws/telemetry` | Conditional | Live telemetry stream |

Auth Required = Yes means the `get_current_principal()` dependency runs. When `MULTI_TENANCY_ENABLED=false` (the default), this dependency returns a synthetic principal without checking a token — no login is needed for local development.

---

## Persistent vs Ephemeral State

### Survives Restarts (Persistent Disk)

| State | Location |
|---|---|
| ChromaDB vectors | `/var/data/chroma_store/` |
| Uploaded CSV files | `/var/data/datasets/` |
| chunks.jsonl | `/var/data/data_processed/` |
| bm25_index.pkl | `/var/data/data_processed/` |

### Does NOT Survive Restarts (Ephemeral / In-Memory)

| State | Notes |
|---|---|
| `_RECOMMENDATION_CACHE` | Last 20 /analyze calls per worker |
| Active WebSocket connections | Clients auto-reconnect |
| `AgentOrchestrator` instance | Rebuilt on first /analyze after restart |
| Sentence-transformer model cache | Reloaded (~80 MB) on first /embed after restart |

---

## Command Reference

| Task | Command | Entry Point |
|---|---|---|
| Backend dev | `cd backend && uvicorn app.main:app --reload --port 8000` | `app/main.py` |
| Backend prod | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `app/main.py` |
| Frontend dev | `cd frontend && npm run dev` | `src/main.jsx` → `App.jsx` |
| Frontend build | `cd frontend && npm run build` | produces `dist/` |
| Frontend preview | `cd frontend && npm run preview` | serves `dist/` |
| Smoke test ingest | `python scripts/smoke_test_ingestion.py` | `app/data/ingestion_pipeline.py` |
| Smoke test embed | `python scripts/smoke_test_embeddings.py` | `app/rag/embeddings.py` |
| Smoke test search | `python scripts/smoke_test_search.py` | `app/rag/hybrid_retriever.py` |
| Smoke test analyze | `python scripts/smoke_test_orchestrator.py` | `app/agents/orchestrator.py` |
| Smoke test eval | `python scripts/smoke_test_eval.py` | `app/evaluation/deepeval_runner.py` |
| Smoke test auth | `python scripts/smoke_test_auth.py` | `app/core/auth.py` |
| Smoke test analytics | `python scripts/smoke_test_analytics.py` | `app/services/analytics_service.py` |
