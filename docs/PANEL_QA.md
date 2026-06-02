# Panel Q&A Prep — Likely Questions & Strong Answers

Grouped by theme. Answers are kept to under 90 seconds spoken time.

---

## A. Architecture & technology choices

**Q1. Why FastAPI instead of Flask or Django?**
Three reasons. One, FastAPI is async-first, which matters for our `/analyze`
endpoint that fans out to retrieval + LLM + evaluation — a sync worker would
block. Two, it generates the OpenAPI spec automatically, so the panel sees a
working Swagger UI without us writing it. Three, pydantic validation on every
request body means malformed input fails at the door, not deep in the stack.
Django would force us to keep ORM, admin, and template machinery we don't use;
Flask would force us to bolt on async, typing, and OpenAPI ourselves.

**Q2. Why ChromaDB and not FAISS or Pinecone?**
FAISS has no metadata filtering — we'd have to bolt on a sidecar SQLite for
region / severity / equipment, which is more code and more failure modes.
Pinecone is cloud-only, costs money per month, and ties the capstone to an
internet connection. Chroma is embedded, persistent, supports metadata
filters natively, and survives restarts on Render's persistent disk.

**Q3. Why hybrid retrieval and not pure semantic search?**
Pure semantic embeddings are great at concepts but weak at exact identifiers
like transformer IDs ("T-104", "F-12") and equipment codes. Pure keyword
search misses paraphrases ("voltage instability" vs "voltage dropped"). We
run both — BM25 keyword and Chroma semantic — and merge with Reciprocal Rank
Fusion at weights 0.6 / 0.4. The result is high recall and high precision.

**Q4. Why a multi-agent system instead of one big LLM prompt?**
Three benefits. First, observability — the response carries an `agent_trace`
showing what each stage contributed, which is critical for explainability.
Second, determinism — only the Recommendation agent calls an LLM; retrieval,
stability scoring, and root-cause derivation are deterministic, so the panel
sees the same numbers every time. Third, cost control — we only pay LLM
tokens for the final synthesis, not for retrieval ranking or anomaly
correlation.

**Q5. Why React + Vite + Tailwind?**
Vite gives us hot reload in under 200ms — important during a live demo.
Tailwind makes the glassmorphism + per-page accent theme expressible without
writing CSS. React's component model maps cleanly to the dashboard's
repeating cards (gauge, pie, heatmap). We avoided Next.js because we don't
need server-side rendering — the backend is the API service, the frontend
is a pure SPA.

---

## B. Data & retrieval

**Q6. How do you chunk the data? Why not row-level?**
Row-level chunks would mean millions of one-second telemetry snapshots, which
bloats the vector store and dilutes retrieval — every search would return
near-duplicates. We aggregate rows into hourly **incident windows** per
region + equipment, then template each window into a natural-language
narrative. That collapses 2 million household rows into around 35 000
incident chunks that match how operators actually think ("the 6 PM peak
event last Tuesday").

**Q7. Why convert telemetry to prose before embedding?**
Sentence-transformer embeddings are trained on natural language — embedding
raw JSON produces poor similarity. A sentence like "voltage of 218 V in
South Zone during evening peak with transformer overload risk" embeds in a
semantically meaningful space and is also human-readable when surfaced as
evidence in the dashboard. Two birds.

**Q8. What if a new dataset is added later?**
Two paths. Drag-drop the CSV in the ETL tab → click Run ETL → the existing
pipeline normalizes it into the common 12-field grid schema, embeds it, and
upserts into Chroma using stable IDs. No code change. If the schema is
exotic enough that the normalizer can't map it, we add a new branch to
`data/normalizer.py` — a ~30 line change.

---

## C. AI quality & safety

**Q9. How do you stop hallucinations?**
Three layers. One, **guardrails** before the LLM ever sees the query — PII
patterns (SSN, credit card) are blocked outright, off-topic queries are
refused. Two, **grounded prompts** — the LLM is told to use ONLY the
retrieved evidence, and we cite incident IDs back to the user. Three,
**evaluation** — every response can be scored on faithfulness (does it
match the evidence?), answer relevancy, and format correctness via the
DeepEval pipeline. The UI shows these scores as badges.

**Q10. What happens if the LLM is down or unavailable?**
The `TemplateProvider` is always available. It derives a structured answer
deterministically from the retrieved chunks + stability scores — the demo
never fails because of a missing API key. In production, we'd add OpenAI
+ Anthropic as primary / secondary, with template as the final fallback.

**Q11. How does PII handling work?**
Two categories. **Blocked** outright: SSN, credit cards, passports, IBANs,
API keys — these have zero value to grid operations and high risk; the
request is refused with a clear message. **Masked** transparently: email,
phone, IPv4 — replaced with `[REDACTED_EMAIL]` etc., then the request
proceeds with the masked text. Names and addresses are NOT masked because
operators legitimately reference them in maintenance logs.

**Q12. How is "explainability" actually delivered?**
Three artifacts per `/analyze` response. (1) The `agent_trace` shows the
five pipeline stages with timing and per-agent summary. (2) The `evidence`
field lists the retrieved incident IDs the answer is grounded in. (3) The
`root_causes[i].evidence` field maps each derived cause back to the specific
chunks that triggered it. Engineers can audit the entire chain.

---

## D. Scale & ops

**Q13. Can this scale to a real utility?**
Yes — three knobs. Horizontally: the backend is stateless except for the
vector store, so we can put multiple uvicorn workers behind a load balancer
and shard Chroma by tenant_id. Vertically: swap ChromaDB for a managed
vector DB (Pinecone or Weaviate) by replacing one file (`rag/vector_store.py`)
behind the same interface. Throughput-wise: a real utility deployment would
move from `template`/`gpt-4o-mini` to a fine-tuned domain model and from
in-memory recommendation cache to Redis.

**Q14. How does multi-tenancy work?**
Every chunk in Chroma carries a `tenant_id` metadata field. The hybrid
retriever filters by tenant — a tenant only sees its own data plus the
shared "default" baseline. Authentication is JWT; the token's claim
specifies the tenant. By default `MULTI_TENANCY_ENABLED=false` so the
capstone demo runs single-tenant — flipping it to `true` immediately
enforces JWT on every endpoint, with zero code change.

**Q15. How do you handle deploy / cold start?**
Render with a `render.yaml`: backend web service + frontend static site +
1 GB persistent disk for Chroma. First boot is ~30 s because of the
sentence-transformers model load — we mitigate with a healthcheck warmup
and `lifespan` initialization. On Render's paid tier the service never
sleeps, eliminating cold start entirely.

---

## E. Evaluation

**Q16. How do you know the recommendations are good?**
The `/evaluate` endpoint runs three things in parallel.
**DeepEval** (when an LLM is available) computes faithfulness, answer
relevancy, and contextual relevancy. **LLM-as-judge** asks a model to score
accuracy / completeness / actionability on a 1–5 scale. **Heuristic
metrics** (always available, no LLM needed) compute deterministic
faithfulness, format correctness, and answer coverage. The UI shows the
aggregate as an "overall %" badge on every answer.

**Q17. Have you done end-to-end testing?**
Every step has a `scripts/smoke_test_*.py` runner: ingestion, embeddings,
search, analyze, orchestrator, analytics, eval, stream. They run
independently of the server. Many of them were sandbox-verified during
build, and a CI hook would just run them all.

---

## F. Trade-offs / honesty

**Q18. What's the biggest weakness?**
The CSV ingestion synthesizes some fields (e.g. `region` for the
stability dataset, which has no native geo column). We're transparent about
this — the source dataset is carried in metadata. In a real utility, the
SCADA stream would supply real regions; the rest of the architecture
doesn't change.

**Q19. What would you build next?**
Two things. First, a feedback loop — let operators thumbs-up or thumbs-down
recommendations, store that as evaluation data, and fine-tune the LLM
prompts. Second, a **forecasting** module — currently we explain past
incidents; the same telemetry + stability score is enough to forecast
near-term failure probability using a simple LSTM or gradient-boosted
model on top.

**Q20. Why not use LangGraph for the agents?**
LangGraph is great when you need conditional branching, retries, or
parallel agents. Our pipeline is strictly sequential (retrieve → analyse
→ recommend), and the orchestrator is ~80 lines — LangGraph would add
a dependency and an abstraction without buying us anything. If we add
conditional escalation (e.g. "if stability < 0.3, also call a forecasting
agent"), we'd revisit.
