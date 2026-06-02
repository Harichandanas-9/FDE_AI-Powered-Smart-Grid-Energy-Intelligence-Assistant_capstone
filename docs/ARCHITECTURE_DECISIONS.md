# Architecture Decisions — AI-Powered Smart Grid Energy Intelligence Assistant

> Document type: Architecture Decision Records (ADR)
> Last updated: June 2026
> Scope: All technology choices made during capstone implementation

Each section documents the decision context, the choice made, the rationale, the tradeoffs accepted, and the alternatives that were considered and rejected.

---

## ADR-01 — Web Framework: FastAPI vs Flask vs Django

### Chosen
FastAPI (v0.115)

### Context
The backend must serve ~17 REST endpoints plus a WebSocket channel. Several endpoints are compute-heavy (embedding generation, LLM calls) and benefit from async I/O. The response contracts are complex nested JSON that should be validated at the boundary. Render's free tier cold-starts every few minutes, so startup time matters.

### Why FastAPI
- **Async-first**: `async def` route handlers allow the process to service multiple requests during LLM network I/O without threads. Critical for the `/analyze` endpoint which awaits an OpenAI call.
- **Pydantic v2 integration**: Every request and response model is declared once as a Pydantic `BaseModel` in `models/schemas.py`. FastAPI validates, coerces types, and generates OpenAPI docs automatically — no separate serialization layer.
- **Auto-generated OpenAPI UI** at `/docs` is used throughout the capstone for live demo and panel testing.
- **Startup/shutdown lifespan hook** (`core/lifespan.py`) lets us build the BM25 index and check component health at boot rather than on the first request.
- **Dependency injection** (`Depends`) cleanly separates auth (`get_current_principal`) from business logic without global state.
- Startup time on Render free tier: ~2–3 s (FastAPI + uvicorn); Django would add ORM layer startup cost.

### Tradeoffs Accepted
- No built-in ORM — acceptable because this project stores state in ChromaDB + JSONL files, not a relational database.
- Smaller ecosystem than Django — acceptable because we need none of Django's batteries (admin, ORM, forms).

### Alternatives Rejected
- **Flask**: Lacks async support and type-validated request/response models out of the box. Adding `flask-pydantic` or `flask-restx` would replicate what FastAPI provides natively.
- **Django**: Heavy ORM + migrations overhead for a project with no relational schema. Django's sync-first architecture requires `ASGI` adapter for async LLM calls, adding complexity.
- **LiteStar**: Newer, similar philosophy to FastAPI. Rejected because ecosystem maturity and community examples are thinner, increasing debugging cost for a time-constrained capstone.

---

## ADR-02 — Vector Store: ChromaDB vs Pinecone vs FAISS vs Weaviate

### Chosen
ChromaDB (v0.5.20+) with persistent disk

### Context
The system must store ~50K 384-dimensional vector embeddings with associated metadata (region, severity, equipment_type, tenant_id, source_dataset). Retrieval must support metadata filtering (e.g., `where={"region": "North Zone"}`). The deployment target is Render's free tier, which provides a 1 GB persistent disk.

### Why ChromaDB
- **Embedded mode with persistence**: ChromaDB runs in-process — no separate server to deploy or manage. The persistent client writes to `/var/data/chroma_store` on the Render disk. Zero ops overhead.
- **Metadata filtering**: Native `where` clause in `query_collection()` enables tenant isolation and incident filtering by region/severity without post-filtering in Python.
- **Multi-tenancy via metadata**: Each chunk carries `tenant_id`. Queries apply a `$or` filter for `[caller_tenant, "default"]` — clean and ChromaDB-native.
- **Python-native API**: `chromadb.PersistentClient` integrates directly with the embedding pipeline without HTTP round-trips.
- **Free tier friendly**: No API key, no remote quota, no per-query cost.

### Tradeoffs Accepted
- Single-node only — ChromaDB embedded cannot scale horizontally. Acceptable for a capstone demo.
- No built-in approximate nearest-neighbour index tuning (HNSW defaults). Acceptable at 50K vectors; ChromaDB uses HNSW internally by default.
- Cold start: first query after a Render sleep wakes the disk; subsequent queries are fast.

### Alternatives Rejected
- **Pinecone**: Managed SaaS, requires an API key and a free-tier index quota (100K vectors at time of implementation). Adds network latency and API cost. Not available offline.
- **FAISS**: Facebook AI Similarity Search is an excellent in-memory index, but it has no built-in metadata filtering and no persistence format that matches our needs without custom serialization code. We would have had to build a metadata sidecar store.
- **Weaviate**: Excellent feature set (GraphQL, modules, multi-modal). Requires a separate container or cloud account. Overkill for 50K vectors; startup complexity not justified for a capstone.
- **Qdrant**: Similar objections to Weaviate — requires a separate server process on Render, consuming one of the two free-tier web service slots.

---

## ADR-03 — Embedding Model: Sentence Transformers vs OpenAI Embeddings

### Chosen
`sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) with a pure-NumPy `HashEmbedder` fallback

### Context
Every chunk generated by the ETL pipeline must be converted to a dense vector. Queries at retrieval time must be embedded with the same model. The system must work on locked-down corporate laptops (no GPU, potentially no torch DLLs) and on Render's free tier.

### Why sentence-transformers/all-MiniLM-L6-v2
- **Free and local**: No per-token API cost. The model is downloaded once to the Python cache (~80 MB) and runs on CPU.
- **Domain adequacy**: MiniLM-L6-v2 was trained on a large diverse corpus. Power-system terminology (voltage, transformer, outage, frequency) maps well to the embedding space — cosine similarity correctly surfaces related incidents.
- **384 dimensions**: Small enough for in-process ChromaDB storage at 50K vectors without memory pressure.
- **sentence-transformers library API**: `SentenceTransformer.encode(texts, normalize_embeddings=True)` returns normalized numpy arrays directly, compatible with ChromaDB's cosine collection.

### HashEmbedder Fallback (`rag/embeddings.py`)
On Python 3.13 + Windows, torch wheels frequently fail with DLL load errors requiring admin rights. The `HashEmbedder` class uses feature-hashing (MD5 hash of unigrams + bigrams mapped to 384 buckets). This gives:
- Zero external dependencies (pure NumPy)
- Recall comparable to MiniLM on the demo corpus when combined with BM25 (the keyword leg handles exact-match precision)
- Deterministic, reproducible embeddings

The embedder is selected automatically at load time: if `sentence_transformers` import succeeds, use MiniLM; otherwise fall back silently.

### Tradeoffs Accepted
- CPU-only inference: embedding 50K rows takes ~5 minutes on a laptop without GPU. Acceptable for a one-time ETL step.
- HashEmbedder loses semantic generalization (e.g., "blackout" and "outage" would not be similar without shared vocabulary). The BM25 leg compensates for this.

### Alternatives Rejected
- **OpenAI `text-embedding-ada-002` / `text-embedding-3-small`**: $0.0001–$0.0004 per 1K tokens. For 50K chunks averaging 80 tokens, that's ~$0.50–$2 per ETL run. Adds an API key requirement and latency for every chunk at ingest time.
- **`all-mpnet-base-v2`**: Better quality than MiniLM but 768-dim vectors (2× storage) and 2–3× slower on CPU. Diminishing returns for a 50K-vector demo corpus.
- **BERT-base**: Not a bi-encoder; cannot produce single sentence embeddings efficiently without pooling layers.

---

## ADR-04 — Orchestration: Custom Pipeline vs LangChain

### Chosen
Custom `AgentOrchestrator` with `BaseAgent` ABC — no LangChain dependency for the agent layer

### Context
The capstone requires a 4-agent sequential pipeline: Retrieval → Stability → Failure → Recommendation. Each agent must record timing, have a stable name, and write into a shared "envelope" dict that the next agent reads.

### Why Custom Orchestration
- **Transparency**: The `agent_trace` list in the envelope (exposed in every `/analyze` response) is built by `BaseAgent.execute()` — timing_ms, status, summary, error fields are all first-class. LangChain's callback system would bury this in events.
- **No magic**: Each agent is a plain Python class. Debugging means reading `orchestrator.py` — 80 lines of clear sequential code. There are no framework abstractions to navigate.
- **Graceful degradation**: Each agent wraps its `run()` in a try/except inside `execute()`. A failing agent logs the error to `agent_trace` and returns the envelope unchanged — the pipeline never aborts. LangChain's default chain raises on failure.
- **Envelope pattern**: The `Dict[str, Any]` envelope accumulates results (retrieved chunks, stability score, root causes, recommendations) across agents. This is simpler than LangChain's `RunnablePassthrough` / `RunnableParallel` for a sequential pipeline.
- **Dependency weight**: LangChain is still used for the LLM provider abstraction (`langchain-openai`, `langchain-anthropic`) in `rag/llm.py`. Restricting its use to LLM I/O only keeps the dependency surface narrow.

### Tradeoffs Accepted
- No built-in retry/backoff at the agent level (handled at the LLM provider level via `tenacity`).
- No graph-based routing (all agents always run). Acceptable: all 4 agents are fast except the LLM call in RecommendationAgent.

### Alternatives Rejected
- **LangChain Agents (AgentExecutor)**: Tool-calling loop is designed for open-ended reasoning, not deterministic sequential pipelines. Adds parsing overhead and LLM calls to decide which tool to invoke next.
- **LangGraph**: Graph-based state machine, powerful but adds significant conceptual complexity. The sequential 4-step pipeline does not justify a graph representation.
- **CrewAI**: Higher-level multi-agent framework. Black-box enough that the `agent_trace` exposure needed for the frontend visualization would be difficult to produce.
- **AutoGen**: Microsoft's conversation-based multi-agent framework. Conversation-style coordination is unnecessary for a deterministic pipeline.

---

## ADR-05 — Retrieval Strategy: BM25 + Semantic Hybrid vs Pure Semantic

### Chosen
Hybrid retrieval: BM25 (`rank-bm25`) + ChromaDB semantic, fused with Reciprocal Rank Fusion

### Context
Grid incident queries fall into two categories:
1. Conceptual: "What causes transformer overload in industrial zones?" (benefits from semantic similarity)
2. Exact-match: "Show incidents in North Zone with critical severity" (benefits from keyword matching)

A pure semantic approach handles (1) but misses (2) when the dataset vocabulary is technical and sparse.

### Why Hybrid
- **BM25 complements semantic**: BM25 excels at exact technical terms (equipment IDs, region names, severity labels) that may not be well-separated in embedding space. Semantic search excels at paraphrase and domain inference.
- **Combined recall**: The union of top-20 semantic + top-20 BM25 candidates gives a wider pool to re-rank. Empirically, about 30–40% of the final top-5 come exclusively from one ranker.
- **Configurable weights**: `RRF_SEMANTIC_WEIGHT=0.6`, `RRF_KEYWORD_WEIGHT=0.4` via env vars. Operators can tune these without code changes.

### Why RRF (Reciprocal Rank Fusion) vs Score Normalization

Different rankers return incompatible score scales: ChromaDB returns cosine distances in [0,1]; BM25 returns term-frequency scores typically in [0,30]. Naive normalization is fragile — an extreme BM25 score from a single term match can dominate. RRF uses ranks instead of scores:

```
score(doc) = sum_over_rankers( weight / (k + rank_in_ranker) )
```

with `k=60` (standard from the TREC literature). This is the same strategy used by major IR systems. It is rank-position stable: a document at rank 1 in both lists scores the same regardless of the raw score magnitudes.

### Tradeoffs Accepted
- BM25 index must be rebuilt after each ETL run. The index is persisted as `bm25_index.pkl` and reloaded on startup from `chunks.jsonl`.
- BM25 does not support metadata filtering natively; post-filtering is applied on BM25 hits where ChromaDB metadata is available.

### Alternatives Rejected
- **Pure semantic (ChromaDB only)**: Misses exact-match queries for region names, severity levels, equipment identifiers.
- **Pure BM25**: Misses conceptual/paraphrase queries. Would require query expansion or synonym dictionaries for the grid domain.
- **TF-IDF + cosine (sklearn)**: Similar to BM25 in-memory but without the probabilistic relevance weighting. BM25 empirically outperforms TF-IDF on domain-specific corpora.
- **Dense Passage Retrieval (DPR)**: Requires training a bi-encoder on in-domain data. No labelled grid query-passage pairs were available for this capstone.

---

## ADR-06 — Frontend Framework: React + Vite vs Next.js vs CRA

### Chosen
React 18 + Vite 5 (SPA, static site deployment)

### Context
The frontend is a data-heavy analytics dashboard with 13 pages, real-time WebSocket telemetry, and animated transitions. It must be deployable as a static site on Render (zero server-side rendering requirement).

### Why React + Vite
- **Vite build speed**: Cold build completes in ~8 s on the capstone laptop vs 30–60 s for CRA (webpack). HMR with Vite is near-instant during development.
- **Static site output**: `npm run build` produces a `dist/` folder that Render serves as a static web service — no Node.js process required, no cold start.
- **React 18 concurrent features**: `useTransition` and `Suspense` handle the async data-loading patterns used across dashboard pages.
- **No server-side rendering needed**: All data comes from the FastAPI backend via REST + WebSocket. SSR would add build complexity without benefit.

### Tradeoffs Accepted
- Client-side routing requires the `rewrite: /* → /index.html` rule in `render.yaml` so direct URL navigation works.
- No built-in image optimization or font optimization (Next.js features). Not needed for this dashboard.

### Alternatives Rejected
- **Next.js**: SSR/SSG adds complexity that is not needed. The API-driven architecture means all pages are equivalent to CSR pages in Next. The file-system routing convention is less flexible than explicit `react-router-dom` route definitions for this layout.
- **Create React App**: Webpack-based, slower build, deprecated by the React team. No reason to choose it over Vite.
- **Svelte / SvelteKit**: Excellent performance characteristics, but unfamiliar to the team and fewer Recharts/Framer Motion integration examples.
- **Vue 3**: Personal preference aside, the Tailwind + Framer Motion ecosystem is more mature on React.

---

## ADR-07 — Styling: Tailwind CSS vs MUI vs styled-components

### Chosen
Tailwind CSS v3 with custom design tokens in `tailwind.config.js`

### Context
The UI uses a dark glassmorphism aesthetic (semi-transparent cards with backdrop blur, per-page accent colors). Consistent theming across 13 pages is required.

### Why Tailwind
- **Utility-first**: Glass card variants (`bg-white/5 backdrop-blur-sm border border-white/10`) are expressed directly in JSX. No context-switching to a CSS file.
- **Custom tokens**: `tailwind.config.js` defines a `glass` color palette and per-page accent colors (e.g., `cyan-500` for Dashboard, `emerald-500` for Grid Stability). One config controls the entire design system.
- **Bundle size**: Tailwind purges unused classes at build time — the CSS bundle is <15 KB for this project.
- **`index.css` component layer**: `.glass`, `.pill`, `.surface` utility classes are defined in `@layer components`, giving reusable class names without the overhead of a CSS-in-JS runtime.

### Tradeoffs Accepted
- Long className strings in JSX (mitigated by extracting reusable component abstractions like `GlassCard`).
- Tailwind requires a PostCSS build step (already provided by Vite).

### Alternatives Rejected
- **Material UI (MUI)**: Rich component library but opinionated design language (Material Design) conflicts with the glassmorphism aesthetic. Customizing MUI themes to remove its visual identity is significant work.
- **styled-components**: Runtime CSS-in-JS adds bundle weight and flash-of-unstyled-content risk. Tailwind's approach is compile-time.
- **Chakra UI**: Same objection as MUI — default visual identity requires extensive theme overrides.
- **Plain CSS modules**: Would require duplicating shared patterns (glass cards, status pills) across many files.

---

## ADR-08 — Charting: Recharts vs D3 vs Chart.js

### Chosen
Recharts v2

### Context
The dashboard needs: line charts (telemetry), area charts (timeline), pie/donut charts (severity), bar charts (per-region), and a custom heatmap grid. All charts must be responsive and theme-able.

### Why Recharts
- **React-native API**: Recharts components are JSX — `<LineChart>`, `<AreaChart>`, `<BarChart>` compose declaratively. No imperative D3 DOM mutations inside `useEffect`.
- **Responsive containers**: `<ResponsiveContainer width="100%" height={300}>` handles window resize automatically.
- **Custom tooltips**: The `content={<CustomTooltip />}` prop accepts a React component, enabling the styled glass-effect tooltips used throughout the dashboard.
- **Theming**: Stroke colors, fill gradients, and axis labels are props — compatible with Tailwind's `text-` and `stroke-` color conventions.

### Custom `HeatmapGrid` component
The heatmap (regions × severity matrix) is not in Recharts' component library. It is implemented as a plain React component with SVG `<rect>` elements whose fill opacity is proportional to the incident count. This was easier than bending a 3rd-party heatmap component to the glass aesthetic.

### Tradeoffs Accepted
- Recharts does not support canvas rendering; SVG performance degrades above ~5K data points. Telemetry line chart is capped at 100 points via `limit` query param.
- Less flexibility than raw D3 for novel chart types (handled by the custom SVG components).

### Alternatives Rejected
- **D3.js**: Excellent for bespoke visualizations but requires imperative DOM manipulation that conflicts with React's virtual DOM. `useEffect` + D3 refs work but are verbose and hard to maintain.
- **Chart.js**: Canvas-based, good performance, but the React wrapper (`react-chartjs-2`) has a different API from Recharts and offers less compositional flexibility for tooltips and labels.
- **Victory**: Similar API to Recharts but heavier bundle (~280 KB vs Recharts ~180 KB) and the grid includes `victory-vendor` with the entire D3 suite.

---

## ADR-09 — Animation: Framer Motion vs CSS Transitions vs React Spring

### Chosen
Framer Motion v11

### Context
Page transitions, card entrance animations, loading states, and the agent trace timeline all require smooth declarative animations.

### Why Framer Motion
- **Declarative `motion.div`**: `initial`, `animate`, `exit` props replace manual CSS class toggling. Staggered children (`staggerChildren: 0.05`) give the card-grid entrance animation in one line of `variants`.
- **`AnimatePresence`**: Enables exit animations when components unmount (e.g., loading spinner fading out when data arrives). CSS transitions cannot animate unmounting elements.
- **Layout animations**: `layout` prop on cards enables smooth reflow when filter results change.
- **Performance**: Framer Motion uses the Web Animations API and `transform`/`opacity` where possible, staying off the layout/paint path.

### Tradeoffs Accepted
- Bundle size: ~120 KB gzipped. Justified by the number of animated surfaces.
- Learning curve for `variants` and `useAnimation`. Well documented.

### Alternatives Rejected
- **CSS transitions/keyframes**: Cannot animate component unmounting. Complex stagger sequences require JavaScript anyway.
- **React Spring**: Physics-based, excellent for interactive gestures. More complex API for the declarative entrance animations used here (page fades, list staggers). Framer Motion's spring defaults are adequate.
- **GSAP**: Professional-grade timeline animation. Overkill for entrance animations; the React integration (via `useGSAP`) adds complexity without benefit over Framer Motion.

---

## ADR-10 — Evaluation: DeepEval + LLM-as-Judge vs Manual Evaluation

### Chosen
DeepEval (`deepeval>=1.5.4`) for automated metric computation + custom LLM-as-judge (`evaluation/llm_judge.py`) with heuristic fallbacks for both

### Context
The capstone requirement specifies both DeepEval and LLM-as-judge evaluation. The evaluation must work even when:
- DeepEval is not installed (optional dependency)
- No LLM API key is configured (offline mode)

### DeepEval Usage (`evaluation/deepeval_runner.py`)
Computes three metrics per analyze response:
- **Faithfulness**: Are the claims in the recommendation grounded in the retrieved context?
- **Answer Relevancy**: Does the recommendation address the query?
- **Contextual Recall**: Are the retrieved chunks the right ones for the query?

DeepEval uses an LLM judge internally. When `OPENAI_API_KEY` is absent, the `deepeval_runner` falls back to heuristic scoring (chunk overlap, keyword coverage).

### LLM-as-Judge (`evaluation/llm_judge.py`)
A separate judge prompt evaluates the recommendation on three dimensions (0–1 each):
- **Accuracy**: Is the recommendation technically correct for the grid domain?
- **Completeness**: Does it cover the identified root causes?
- **Actionability**: Are the recommended actions specific and executable?

When no LLM is available, the judge falls back to rule-based heuristics (presence of domain action keywords, structured step count).

### Why Heuristic Fallbacks
The evaluation system must produce scores in the UI even during offline demos or when the API key has expired. A fallback that produces 0.0 scores would mislead the panel. Heuristic fallbacks produce plausible scores and are clearly labelled as `"mode": "heuristic"` in the response.

### Tradeoffs Accepted
- LLM-as-judge evaluations are themselves non-deterministic and subject to the judge model's biases.
- DeepEval metrics add ~1–2 s latency to the `/evaluate` endpoint when an LLM is available.

### Alternatives Rejected
- **RAGAS**: Similar capabilities to DeepEval but requires more setup (question/answer/context triplets in specific formats). DeepEval's API is simpler for per-query evaluation.
- **Human evaluation only**: Not scalable for a demo where the panel may submit 10+ queries.
- **BLEU/ROUGE**: N-gram overlap metrics are poor proxies for recommendation quality. A recommendation can be high quality while using different vocabulary than the reference.

---

## ADR-11 — Auth: JWT + Multi-Tenancy vs API Key vs No Auth

### Chosen
JWT (HS256, PyJWT) with optional multi-tenancy (`MULTI_TENANCY_ENABLED` env var)

### Context
The system supports multiple utility company tenants (demo users: `admin`, `acme`, `globex`). Each tenant's ChromaDB data is isolated by `tenant_id` metadata. The auth layer must be disabled by default for single-tenant local development.

### Design
- `POST /api/v1/auth/login` accepts `{username, password}` from `DEMO_USERS` env var (JSON dict). Returns a JWT with `{username, tenant_id, role, exp}` claims.
- `get_current_principal()` FastAPI dependency extracts the principal from the `Authorization: Bearer <token>` header. When `MULTI_TENANCY_ENABLED=false`, it returns a synthetic `{"username": "default", "tenant_id": "default", "role": "admin"}` without checking the token — zero friction for local dev.
- JWT expiry: 480 minutes (8 hours) — long enough for a day's demo session.
- WebSocket auth: token passed as `?token=` query param; validated only when multi-tenancy is enabled.

### Why HS256 over RS256
Single shared secret (`JWT_SECRET` env var). RS256 would require managing a key pair and distributing the public key. Overkill for a demo with 3 hardcoded users.

### Tradeoffs Accepted
- Demo users are defined in an env var as JSON — not a real user store. Production would replace this with a database-backed user service.
- No refresh token mechanism. Sessions expire after 8 hours.

### Alternatives Rejected
- **API keys**: Simpler, but cannot carry tenant_id or role claims. Would require a separate lookup.
- **OAuth2 / OIDC**: Correct for production, but requires an identity provider (Auth0, Keycloak). Adds significant operational complexity for a capstone demo.
- **No auth**: Unacceptable — the multi-tenancy isolation requirement mandates some credential check.

---

## ADR-12 — LLM Provider: Template Fallback Design

### Chosen
Three-provider strategy with automatic fallback: OpenAI → Anthropic → TemplateProvider

### Context
LLM calls may fail (no API key, quota exhausted, network error). The system must produce a usable recommendation in all cases — the RecommendationAgent must never return an empty response to the user.

### Provider Selection (`rag/llm.py`)
`get_provider(settings)` returns a provider object based on `LLM_PROVIDER` env var:
- `openai` → `langchain-openai` `ChatOpenAI(model=LLM_MODEL)` (default: `gpt-4o-mini`)
- `anthropic` → `langchain-anthropic` `ChatAnthropic(model=LLM_MODEL)`
- `ollama` → `langchain-community` `ChatOllama(base_url=OLLAMA_BASE_URL)`

### TemplateProvider Fallback
When the configured provider's API key is absent or the import fails, `get_provider()` falls back to `TemplateProvider` — a deterministic Python class that generates a structured recommendation from the envelope contents (root causes, stability score, retrieved chunk summaries) using string templates. This provider:
- Requires no network access
- Always returns valid JSON matching the response schema
- Is clearly labelled as `"provider": "template"` in the response

The health endpoint reports `"llm": "fallback_template"` (classified as `HEALTHY` — this is by design, not an error).

### Tradeoffs Accepted
- Template-generated recommendations are formulaic compared to LLM output. Adequate for demos without an API key.
- The fallback does not support streaming — acceptable since the `/analyze` endpoint returns full JSON.

### Alternatives Rejected
- **Crash on missing API key**: Unacceptable — would break the demo for any panelist running without an API key.
- **Single provider, no fallback**: Same objection.
- **Ollama as primary**: Requires a running Ollama server. Appropriate for local deployment but not for Render where no GPU is available.

---

## ADR-13 — Chunking Strategy: Aggregated Hourly Windows vs Character-Based Chunks

### Chosen
Aggregated hourly incident windows (via `data/aggregator.py`) — each chunk is one JSON record representing a single time window's statistics

### Context
The source datasets are tabular (CSV rows of voltage, frequency, stability, demand readings). Converting these to text for embedding requires a decision about granularity.

### Why Hourly Aggregation
- **Semantic coherence**: One hour of grid readings at a substation forms a coherent "incident window". Splitting at character boundaries would separate related readings.
- **Metadata richness**: Each aggregated row carries meaningful metadata: `voltage_mean`, `voltage_std`, `frequency_mean`, `stability_score_mean`, `demand_max`, `outage_event`, `transformer_status`, `region`, `severity`. These fields become ChromaDB metadata for filtering.
- **Templated narrative** (`data/templater.py`): Each window is converted to a natural-language sentence: "In the North Zone at 14:00, voltage averaged 228.5V (nominal: 230V), frequency was 49.8Hz, stability index was -0.12 (unstable), and transformer status was overload_risk." This ensures the embedding captures the operational context.
- **Token efficiency**: One window = one chunk = one embedding. No overlap calculation needed. The `final_top_k=5` limit keeps the prompt within token budget.

### Tradeoffs Accepted
- Sub-hour patterns are smoothed out. A 10-minute voltage spike within an hour would appear as an elevated `voltage_std`. Acceptable for incident-level retrieval.
- Chunk text is synthetic (generated from statistics), not verbatim from a document. The LLM prompt explicitly marks retrieved context as "telemetry summaries".

### Alternatives Rejected
- **Character-based chunking (e.g., 512 chars, 50-char overlap)**: Designed for long-form text documents. Tabular data converted to a long CSV string would be split mid-row, losing row context.
- **Row-per-chunk (no aggregation)**: Would produce 500K+ chunks for the full datasets, bloating ChromaDB and increasing retrieval latency with no quality improvement — minute-level readings are too granular for incident-level queries.
- **Paragraph splitting (langchain RecursiveCharacterTextSplitter)**: Same objection as character-based — our data is structured, not prose.

---

## ADR-14 — Agent Pipeline Topology: Sequential vs Parallel vs Graph

### Chosen
Sequential pipeline: Guardrails → Retrieval → Stability → Failure → Recommendation

### Context
The four agents have a strict data dependency chain:
- StabilityAgent reads `envelope["retrieved"]` (output of RetrievalAgent)
- FailureAgent reads `envelope["stability_analysis"]` (output of StabilityAgent)
- RecommendationAgent reads `envelope["root_causes"]` and `envelope["retrieved"]`

### Why Sequential
- **Data dependencies**: The dependency chain is linear. Parallelism would require all agents to receive the same initial data and produce independent outputs — not the case here.
- **Simplicity**: `for agent in self.agents: envelope = agent.execute(envelope)` is six lines and trivially debuggable.
- **Timing visibility**: The sequential execution means `agent_trace` timing entries are naturally ordered and cumulative, giving the frontend a clear pipeline visualization.
- **Total latency**: The bottleneck is the RecommendationAgent (LLM call, ~500ms–2s). The three deterministic agents (Retrieval, Stability, Failure) add <50ms total. Parallelism would not reduce the critical path.

### Tradeoffs Accepted
- No speculative execution: all agents always run, even if a previous agent's output would make a subsequent agent's work redundant. Acceptable — each agent is fast except the LLM call.
- No conditional branching: the pipeline cannot short-circuit to a different path based on query type. Acceptable for the current 4-agent design.

### Alternatives Rejected
- **Parallel execution (asyncio.gather)**: Would require merging independent outputs — not appropriate when each agent enriches the shared envelope.
- **LangGraph state machine**: Graph-based routing enables conditional paths and cycles. Justified for complex reasoning agents; unnecessary for a linear 4-step pipeline.
- **Map-reduce pattern**: Applicable if multiple independent retrieval strategies ran in parallel before a merge. Future enhancement candidate if agent count grows.

---

## Summary Decision Matrix

| Decision | Chosen | Key Reason |
|---|---|---|
| Web framework | FastAPI | Async, Pydantic validation, OpenAPI docs |
| Vector store | ChromaDB | Embedded, persistent, metadata filtering, free |
| Embedding model | all-MiniLM-L6-v2 + HashFallback | Free, local, fallback for no-torch environments |
| Agent orchestration | Custom pipeline | Transparent, graceful degradation, trace exposure |
| Retrieval strategy | BM25 + Semantic + RRF | Handles both exact-match and conceptual queries |
| Score fusion | RRF (rank-based) | Scale-invariant; works with mismatched ranker scores |
| Frontend framework | React 18 + Vite | Fast build, static deployment, ecosystem |
| Styling | Tailwind CSS | Utility-first, purged bundle, custom tokens |
| Charts | Recharts | React-native API, responsive containers |
| Animation | Framer Motion | Declarative, exit animations, layout transitions |
| Evaluation | DeepEval + LLM-as-judge + heuristic fallback | Automated, works offline |
| Auth | JWT + multi-tenancy toggle | Tenant isolation, zero friction for local dev |
| LLM provider | OpenAI / Anthropic / TemplateProvider | Works with or without API key |
| Chunking | Aggregated hourly windows | Semantic coherence, rich metadata |
| Agent topology | Sequential pipeline | Linear dependency chain, debuggable |
