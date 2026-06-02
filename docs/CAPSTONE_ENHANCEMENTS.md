# Capstone Enhancements — AI-Powered Smart Grid Energy Intelligence Assistant

> Document type: Enhancement Record
> Last updated: June 2026
> Scope: All features added beyond the base capstone specification

This document describes each enhancement in detail: what was added, how it works technically, and why it improves the capstone submission.

---

## Enhancement 1 — Predictive Grid Failure Intelligence

### What Was Added

A new endpoint `GET /api/v1/predict` and a corresponding frontend page `PredictiveIntelligence.jsx` at route `/predict`.

**Files changed / created:**
- `backend/app/api/routes_predict.py` (new)
- `frontend/src/pages/PredictiveIntelligence.jsx` (new)
- `backend/app/main.py` (router registration added)
- `frontend/src/App.jsx` (route added)

### How It Works

The prediction engine is a deterministic rule-based analyser that reads up to 5,000 of the most recent telemetry chunks from ChromaDB via `analytics_service._fetch_all()` and computes a composite risk score per region.

**Risk components (weighted sum):**

| Component | Weight | Calculation |
|---|---|---|
| Voltage risk | 30% | `abs(avg_voltage - 230V) / 230V` normalised to [0,1] over 10% deviation threshold |
| Frequency risk | 20% | `abs(avg_freq - 50Hz)` normalised to [0,1] over 1 Hz max deviation |
| Stability risk | 25% | Derived from the stability index mean: `max(0, (-avg_stability + 1) / 2)` |
| Outage risk | 15% | Fraction of windows with `outage_event=1` |
| Overload risk | 10% | Fraction of windows with `transformer_status=overload_risk` |

**Risk levels:** `critical` (≥0.75), `high` (≥0.55), `medium` (≥0.35), `low` (<0.35)

Each region receives:
- `risk_score` (0–1 composite)
- `risk_level` string
- `alerts` list (human-readable alert messages)
- `recommendations` list (prioritised action items with category tags)

The overall prediction merges all regions. `global_alerts` surfaces only the `critical` and `high` risk regions for the dashboard banner.

**Response shape:**
```json
{
  "status": "ok",
  "overall": { "risk_score": 0.42, "risk_level": "medium", ... },
  "per_region": { "North Zone": {...}, "South Zone": {...} },
  "global_alerts": ["Region 'North Zone': HIGH risk (0.62) — ..."],
  "highest_risk_region": "North Zone",
  "n_incidents_analysed": 3847,
  "n_regions": 5
}
```

**Frontend page:** `PredictiveIntelligence.jsx` displays:
- Overall risk gauge with animated score
- Per-region risk cards with colour-coded severity
- Prioritised alert list
- Recommended actions grouped by category (voltage, frequency, transformer, stability, outage, demand)

### Why This Improves the Capstone

The base specification required "Proactive intelligence on grid failures" as a Requirement 2 item but did not specify a dedicated endpoint or UI. This enhancement:
1. Demonstrates that the system can act **proactively** — not just answer queries, but surface predicted risks from historical patterns without a user prompt
2. Shows algorithmic risk scoring grounded in real telemetry metadata
3. Provides a distinct UI surface that panel evaluators can interact with independently of the query console
4. Requires no LLM call — proving the system adds value even in offline / no-API-key mode

---

## Enhancement 2 — AI Explainability Engine

### What Was Added

Enhanced `AgentVisualization.jsx` to display the complete agent reasoning trace with evidence, similarity scores, timing bars, and per-agent output summaries.

**Files changed:**
- `frontend/src/pages/AgentVisualization.jsx` (enhanced)
- `frontend/src/components/charts/AgentFlow.jsx` (timing bar support)

### How It Works

The `/analyze` endpoint already returns a full `agent_trace` array in every response, where each entry contains:

```json
{
  "agent": "retrieval_agent",
  "status": "ok",
  "duration_ms": 142,
  "summary": "Retrieved 5 incidents; top similarity 0.847",
  "error": null
}
```

The enhanced `AgentVisualization.jsx`:

1. **Accepts a query input** and calls `POST /api/v1/analyze` directly, storing the full response.

2. **Timeline with timing bars**: Each agent is rendered as a horizontal bar whose width is proportional to `duration_ms` relative to the total pipeline duration. Bars are colour-coded by agent (cyan for retrieval, amber for stability, orange for failure, emerald for recommendation, blue for guardrails).

3. **Per-agent output panels**: Clicking an agent card expands it to show:
   - `summary` string from the trace
   - For `retrieval_agent`: the list of retrieved chunks with their `score` (RRF fusion score), `semantic_rank`, `keyword_rank`, and the first 200 characters of the chunk text
   - For `stability_agent`: the `stability_analysis` object (overall score, voltage deviation, frequency deviation, assessment)
   - For `failure_agent`: the `root_causes` list with `cause`, `probability`, and `evidence` chunk IDs
   - For `recommendation_agent`: the full structured recommendation with action steps

4. **Evidence section**: Retrieved chunks are displayed in a collapsible panel showing metadata (region, severity, equipment_type) and the narrative text, enabling the user to verify that the recommendation is grounded in real data.

5. **Similarity score display**: Each retrieved chunk shows its RRF fusion score and which retriever(s) contributed to its ranking (semantic only, keyword only, or both).

### Why This Improves the Capstone

- **Interpretability**: Evaluation panels consistently ask "how does the AI decide?" This page answers that question without the user having to read code.
- **Demonstrates RAG grounding**: The evidence panel proves the LLM answer is not hallucinated — it traces directly to specific chunks with their source dataset, region, and severity metadata.
- **Shows A2A communication**: The timing bar makes visible that four distinct agents are running in sequence and contributing different types of analysis to the final answer.
- **Aligns with advanced requirement**: The Requirement 2 item "LLM-as-judge for mitigation validation" is complemented by this transparency — users can judge the recommendation quality themselves by inspecting the evidence.

---

## Enhancement 3 — ETL Status Reliability

### What Was Added

Two-layer fix to ensure the ETL status is accurately reflected in both the backend health check and the frontend UI, even when the `etl_history.jsonl` file is absent.

**Files changed:**
- `backend/app/api/routes_ingest.py` (ChromaDB fallback in `/ingest/status`)
- `frontend/src/pages/ETL.jsx` (cache-busting, localStorage signal)
- `frontend/src/pages/Dashboard.jsx` (`etlEffectivelyRan` fallback logic)

### How It Works

**Root cause of the bug:** The original implementation stored ETL history in `etl_history.jsonl`. If the backend was redeployed after ETL had run (Render redeploys clear the ephemeral filesystem unless the disk is configured correctly), or if the ETL ran in an earlier development iteration before history tracking was added, the history file was absent and the API returned `{last_run: null}`.

**Backend fix — ChromaDB fallback:**

The `/api/v1/ingest/status` endpoint now:
1. Checks for `etl_history.jsonl` (primary)
2. If absent, queries ChromaDB for the total chunk count
3. If ChromaDB has chunks (`n > 0`), synthesises a status record: `{last_run: "inferred_from_chroma", n_incidents: n, status: "ok"}`
4. Returns this synthesised record so the frontend can determine that ETL has run

**Frontend fix — cache-busting:**

The `EtlLastRun()` API wrapper in `api.js` appends `?_t=<rotating_timestamp>` to the GET request, where the timestamp rotates every 10 seconds. This prevents Axios's default caching from serving a stale `{last_run: null}` response after ETL completes.

`ClearEtlCache()` is called immediately after a successful ETL run to force the next status poll to hit the network.

**Frontend fix — Dashboard fallback logic:**

`Dashboard.jsx` evaluates `etlEffectivelyRan` as:
```javascript
const etlEffectivelyRan = (etlStatus?.last_run !== null) || (stats?.n_incidents > 0);
```

This means: even if the history file is absent, if the dashboard's `/grid-score` response shows incidents in the database, the UI treats ETL as having completed and renders the live data panels instead of the "Run ETL first" prompt.

### Why This Improves the Capstone

- **Demo reliability**: The most common failure mode during capstone demos is ETL showing "Yet To Run" despite the data being present. This fix eliminates a class of confusing UI states that would require explanation during the presentation.
- **Production robustness**: On Render, a redeploy clears the ephemeral filesystem. The ChromaDB fallback means the status is inferred from the persistent disk data rather than from a file that may not survive the redeploy.
- **Correct UX**: Users should never see conflicting signals (database has data but UI says ETL hasn't run). The multi-layer fallback ensures consistency.

---

## Enhancement 4 — Smart Meter Anomaly Detection

### What Was Added

Enhanced `SmartMeter.jsx` with threshold-based anomaly classification, per-incident severity badges, expandable incident detail panels, and anomaly trend charts.

**Files changed:**
- `frontend/src/pages/SmartMeter.jsx` (significantly enhanced)

### How It Works

The Smart Meter page calls `GET /api/v1/incidents?source=household_power` to retrieve household consumption incidents from ChromaDB, then applies client-side threshold analysis:

**Anomaly thresholds applied:**

| Anomaly Type | Condition | Badge |
|---|---|---|
| Over-voltage | `voltage_mean > 242V` (>5% above 230V nominal) | Red "OVER-VOLTAGE" |
| Under-voltage | `voltage_mean < 207V` (>10% below nominal) | Orange "UNDER-VOLTAGE" |
| High demand | `demand_max > 95th percentile` of dataset | Purple "HIGH DEMAND" |
| Frequency deviation | `abs(frequency_mean - 50) > 0.5 Hz` | Yellow "FREQ DRIFT" |
| Transformer stress | `transformer_status == "overload_risk"` | Red "OVERLOAD RISK" |

**Per-incident expanded view:**
Clicking an incident card expands it to show:
- Voltage, frequency, and stability readings with deviation from nominal
- Active anomaly badges
- The raw incident text (the natural-language narrative generated at ETL time)
- Source dataset and metadata (region, severity, equipment_type)

**Anomaly summary statistics:**
A header section shows totals: number of over-voltage events, under-voltage events, high demand events, and overall anomaly rate.

**Trend chart:**
A `TelemetryLineChart` shows voltage and demand over the incident timeline for the current filtered set.

### Why This Improves the Capstone

- **Directly satisfies Requirement 2**: "Telemetry anomaly correlation analysis" — the threshold analysis correlates voltage deviations with other indicators and classifies incident types.
- **Visual differentiation**: The base implementation displayed a plain list of incidents. The badge-and-expand pattern gives evaluators an immediately readable summary of grid health at the meter level.
- **Supports the household dataset**: The `household_power_consumption.csv` dataset was included in the specification. This page demonstrates that it is actually used and produces meaningful output.

---

## Enhancement 5 — Enhanced Multi-Agent Visualization

### What Was Added

The `AgentFlow.jsx` chart component was upgraded to support timing bars, and the `AgentVisualization.jsx` page was restructured to show per-agent output panels alongside the flow diagram.

**Files changed:**
- `frontend/src/components/charts/AgentFlow.jsx` (timing bar support)
- `frontend/src/pages/AgentVisualization.jsx` (full restructure)

### How It Works

**AgentFlow chart (`components/charts/AgentFlow.jsx`):**

The component accepts the `agent_trace` array from an `/analyze` response. It renders:
- A horizontal pipeline of agent nodes connected by arrows (SVG-based)
- Below each node: a proportional timing bar showing that agent's `duration_ms` as a fraction of total pipeline duration
- Colour coding: green for `status: ok`, red for `status: error`, yellow for `status: refused`
- Agent icons: distinct icon per agent type (shield for guardrails, search for retrieval, activity for stability, zap for failure, lightbulb for recommendation)

**AgentVisualization page (`pages/AgentVisualization.jsx`):**

The page is split into two columns:
- Left: query input + AgentFlow chart + overall pipeline timing
- Right: per-agent output panels (collapsible)

The right column panels show the specific data each agent contributed:
- **Guardrails panel**: Shows whether the query was allowed, any PII that was masked, and the masked query that was passed downstream
- **Retrieval panel**: Shows all 5 retrieved chunks with RRF scores, semantic rank, keyword rank, source metadata
- **Stability panel**: Shows grid health score, voltage deviation, frequency deviation, stability assessment
- **Failure panel**: Shows root causes with probability percentages and evidence chunk references
- **Recommendation panel**: Shows the full structured recommendation with action steps and confidence score

### Why This Improves the Capstone

- **Makes A2A communication tangible**: The panel evaluators can see exactly what information each agent passed to the next, demonstrating that the pipeline is genuinely multi-agent rather than a single LLM call.
- **Debuggability**: During the demo, if a recommendation is unexpected, the evidence panel immediately shows which chunks were retrieved and why — supporting a live walkthrough.
- **Timing transparency**: The timing bars show that the retrieval + stability + failure agents are fast (deterministic, <50ms each) while the recommendation agent is where the LLM latency appears. This demonstrates that the system design separates fast computation from slow LLM inference.

---

## Enhancement 6 — Deployment Completeness

### What Was Added

`render.yaml` was completed with the full frontend static site service definition and the persistent disk configuration.

**Files changed:**
- `render.yaml` (frontend service and disk config added)

### How It Works

The original `render.yaml` contained only the backend service definition. The frontend static site and the persistent disk were left as TODOs. The completed `render.yaml` adds:

**Frontend static site service:**
```yaml
- type: web
  name: smart-grid-frontend
  runtime: static
  rootDir: frontend
  buildCommand: npm ci && npm run build
  staticPublishPath: dist
  autoDeploy: true
  envVars:
    - key: VITE_API_URL
      value: https://smart-grid-backend.onrender.com
  routes:
    - type: rewrite
      source: /*
      destination: /index.html
```

The `routes` rewrite rule is required for React Router's client-side routing — without it, navigating directly to `/query` or `/predict` returns a 404 from the static file server.

**Persistent disk on the backend service:**
```yaml
disk:
  name: chroma-disk
  mountPath: /var/data
  sizeGB: 1
```

The disk mounts at `/var/data`. The backend env vars `DATA_DIR=/var/data/datasets` and `CHROMA_PERSIST_DIR=/var/data/chroma_store` point into this mount. Without the persistent disk, ChromaDB data is erased on every service redeploy.

### Why This Improves the Capstone

- **One-command deployment**: With a complete `render.yaml`, the entire stack (backend + frontend + disk) can be deployed from the Render dashboard with a single "Blueprint" sync.
- **Production correctness**: Without the disk config, the capstone deployment would lose all embedded data on every git push. This is a critical production correctness fix.
- **Evaluation readiness**: Panel evaluators who attempt to deploy the project independently will get a working system without needing to manually configure the disk or frontend service.
