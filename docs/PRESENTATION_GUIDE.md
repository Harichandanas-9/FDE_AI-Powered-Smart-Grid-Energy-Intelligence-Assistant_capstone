# Presentation Guide — 10-Minute Demo Flow

This is the runbook for the panel presentation. Times include speech.
**Total: 10 minutes** (8 min demo + 2 min Q&A).

---

## Pre-flight (do this 5 min before the panel starts)

1. **Backend running** on port 8000 — terminal 1. Hit `/api/v1/health` once
   to warm the sentence-transformers model.
2. **Frontend running** on port 5173 — terminal 2.
3. **Datasets present** in `datasets/` — at least
   `smart_grid_stability_augmented.csv`.
4. **ETL run** at least once so the dashboard isn't empty (Run the
   "Refresh Data" button on the Dashboard).
5. **Browser tabs open**:
   - Tab 1: `http://localhost:5173/` (Dashboard)
   - Tab 2: `http://localhost:8000/docs` (Swagger — backup)
   - Tab 3: `docs/ARCHITECTURE.md` (open in a markdown viewer for fallback)

---

## 1 · OPENING (0:00 – 0:45)

> *"Utility engineers spend hours correlating SCADA logs, smart-meter
> readings, and outage reports just to investigate one grid incident.
> We built an AI assistant that lets them ask in natural language and
> get a grounded, explainable answer with mitigation recommendations.
> Today I'll show you the live system — multi-agent reasoning over real
> Kaggle and UCI grid datasets — and we'll trace exactly how the AI
> arrives at its answer."*

**Action:** show the Dashboard tab.

**What's on screen:** Glass-effect sidebar, KPI tiles, gauge, region bars,
timeline area chart, heatmap, recent recommendations card.

---

## 2 · DATA PIPELINE — THE ETL TAB (0:45 – 2:00)

**Talking points:**
- "We use three datasets: Smart Grid Stability from Kaggle, Household
  Electric Consumption from UCI, and Electric Power Consumption."
- "The ETL tab lets engineers upload more CSVs or re-process existing ones."
- "When I click Run ETL, the backend: parses the CSV with a delimiter
  sniffer, normalizes each row to a common 12-field grid schema, groups
  rows into hourly incident windows, converts each window into a
  natural-language narrative, embeds it with sentence-transformers, and
  upserts into ChromaDB."

**Action:** click on the ETL tab. Show the list of files. Click **Run ETL**
on one row. Wait for the toast.

**What to highlight in the toast:** "Ingested N chunks · Vectors=M · 2.3 s"

---

## 3 · DASHBOARD WALKTHROUGH (2:00 – 3:30)

**Action:** return to Dashboard. Walk through the widgets left-to-right,
top-to-bottom.

**Talking points per widget:**
- **KPI tiles:** "Health score, incidents indexed, outages, regions tracked
  — at-a-glance state."
- **Health gauge:** "Score computed from voltage deviation, frequency drift,
  stability score, and outage count — animated by Framer Motion."
- **Region bars (clickable):** "Click any region — it filters the Failure
  Analysis page to that region. Cross-page navigation, not a static view."
- **Timeline area chart:** "Severity stacked over time. Reveals patterns
  like 'we had three critical events in the same evening last week'."
- **Heatmap:** "Region × severity. Click a cell — opens Heatmap Analytics
  with the matching incidents."

---

## 4 · NATURAL-LANGUAGE QUERY — THE BIG ONE (3:30 – 5:30)

**Action:** click **Query Console** in the sidebar.

**Talking points:**
- "This is where it matters. An operator types in plain English."
- (Already pre-filled.) "Let me send: 'Voltage instability is increasing
  in South Zone during evening peak demand. What are the likely causes?'"

**Action:** click **Send**.

**What happens on screen, narrate as it animates:**
1. The operator's question appears as a chat bubble.
2. After ~1–2 seconds, the bot's response renders.
3. **Side panel updates** with three glass cards:
   - **Agent trace** — five stages, each with timing and a one-line summary
   - **Root causes** — with probabilities and evidence chunk IDs
   - **Retrieved evidence** — the actual incident records the LLM used

**Talking points:**
- "The agent trace shows five distinct stages — guardrails, retrieval,
  stability analysis, failure analysis, recommendation. Each is a separate
  Python module, each timed independently."
- "The agents are deterministic — only the recommendation agent calls an
  LLM. That means the **same query produces the same root causes every
  time** — important for explainability and reproducibility."
- "Notice every root cause carries its evidence chunk IDs. An engineer can
  audit exactly which historical incidents drove this answer."

---

## 5 · GUARDRAILS DEMO (5:30 – 6:00)

**Action:** type a clearly off-topic query: *"What's the weather today?"*
and send.

**What appears:** A refusal banner — "I can only answer smart-grid questions…"

**Action:** type *"My SSN is 123-45-6789, check voltage in South Zone"*.

**What appears:** A blocked banner — "I cannot process this query because it
contains sensitive personal data (ssn)."

**Talking point:** *"Off-topic queries and personally identifiable info
never reach the LLM — this matters for compliance in real utility
deployments."*

---

## 6 · EVALUATION + PDF EXPORT (6:00 – 7:00)

**Action:** scroll back to the on-topic answer. Click **Run evaluation** on
the answer bubble.

**What appears:** three pills + overall score — `faith N% · judge N% · fmt
N% · overall N% (via heuristic)`.

**Talking points:**
- "Three evaluators run in parallel: DeepEval for faithfulness and
  contextual relevancy, an LLM-as-judge for actionability, and heuristic
  metrics that work offline. The badge shows the aggregate."

**Action:** click the **PDF** button on the answer.

**What happens:** Browser downloads `analysis_YYYYMMDD_HHMMSS.pdf`. Open it
to show a clean 1-page report with query, answer, causes, recommendations,
evidence, and agent trace.

**Talking point:** *"Engineers can attach this to their ticket system."*

---

## 7 · MULTI-AGENT VISUALIZATION (7:00 – 7:45)

**Action:** open the **Agent Flow** tab. Click **Run** with the pre-filled
query.

**What appears:** A horizontal pipeline of five glass cards with arrows
between them — guardrails → retrieval → stability → failure → recommendation
— each animated in.

**Talking points:**
- "Same query, but here we focus on the agent communication. Watch the
  timing on each stage: guardrails sub-millisecond, retrieval ~50 ms,
  recommendation a few hundred ms when the LLM is called."
- "This is the agent-to-agent envelope — a shared dict each agent reads and
  writes. The trace is part of the response, so the UI doesn't need to
  guess anything."

---

## 8 · REAL-TIME TELEMETRY (7:45 – 8:15)

**Action:** open the **Telemetry** tab. Toggle from **Poll** to **Live (WS)**.

**What happens:** WS status flips to "open"; the line charts start updating
in real time as the synthetic telemetry simulator streams ticks at 2 Hz.

**Talking point:** *"WebSocket-based simulation today; plug in a SCADA
connector and it's a live grid feed tomorrow — no UI change needed."*

---

## 9 · CLOSING (8:15 – 8:45)

**Action:** return to the Dashboard.

> *"Recap: the system ingests three real grid datasets, retrieves
> historical incidents with hybrid search, runs four specialized agents,
> explains the root cause with cited evidence, generates mitigation
> recommendations, evaluates its own output, supports multi-tenancy, and
> exports the whole thing as a PDF. The code is modular, the deploy is
> one render.yaml away, and the UI is presentation-ready. Happy to take
> your questions."*

---

## 10 · Q&A BUFFER (8:45 – 10:00)

Use `docs/PANEL_QA.md` as the cheat sheet — 20 likely questions are
pre-answered there.

---

## If something breaks live

| Symptom | Recovery |
|---|---|
| Backend stops responding | `Ctrl+C`, `uvicorn app.main:app --reload` again — boot is ~3 s with warm caches |
| Frontend not refreshing | `npm run dev` in the frontend terminal; the previous tab will hot-reload |
| LLM API throws | The TemplateProvider fallback kicks in automatically — the demo continues |
| Chroma collection empty | Open ETL tab → Run ETL on `smart_grid_stability_augmented.csv` |
| Total disaster | Show `docs/ARCHITECTURE.md` Mermaid diagrams as the fallback story |

---

## Demo data — pre-cooked queries to read from

If the panel asks you to type a query, use one of these (proven to give a
rich answer):

1. *"Voltage instability is increasing in South Zone during evening peak
   demand. What are the likely causes?"*
2. *"Transformer overloads are recurring during peak demand — what mitigation
   do you recommend?"*
3. *"Smart meter anomalies detected in a residential service area. What
   should we investigate?"*
4. *"Renewable energy variability is causing grid balancing issues."*
5. *"Unexpected power fluctuations observed after maintenance activity."*

All five appear (slightly paraphrased) in the original requirements document
— so the panel knows we built to spec.
