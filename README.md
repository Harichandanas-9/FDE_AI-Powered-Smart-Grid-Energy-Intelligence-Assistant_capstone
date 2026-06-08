# ⚡ AI-Powered Smart Grid Energy Intelligence Assistant

> A full-stack AI platform that helps power grid operators diagnose faults, analyse telemetry, predict failures, and get instant evidence-backed recommendations — powered by RAG, multi-agent AI, and Groq LLM.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11–3.13
- Node.js 18+
- Groq API key (free at https://console.groq.com)

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-ml.txt

# Configure environment
# Edit .env and set your GROQ_API_KEY (remove leading space if present)
# GROQ_API_KEY=gsk_your_key_here

# Start backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Open Browser
```
http://localhost:5173
```

### 4. First-time Data Setup
1. Go to **ETL tab**
2. Select `smart_grid_stability_augmented.csv`
3. Click **Ingest**
4. All tabs will populate with live data

---

## 🏗️ Architecture

```
CSV Datasets → ETL Pipeline → BM25 Index + JSONL
                                      ↓
User Query → Guardrails → Retrieval → Stability Analysis
                                          → Failure Analysis
                                            → Groq LLM Recommendation
                                              → DeepEval Scoring
```

### Pipeline Flow
| Step | Agent | Technology | Purpose |
|------|-------|-----------|---------|
| 1 | ETL | pandas | Load, clean, aggregate CSV → 100 chunks |
| 2 | BM25 Index | rank-bm25 | Build keyword search index |
| 3 | Guardrails | regex | Block PII, injection, off-topic |
| 4 | Retrieval | BM25 + text fallback | Find top-5 relevant incidents |
| 5 | Stability | Python math | Grid Health Score 0–100 |
| 6 | Failure | Rule-based | Root cause identification |
| 7 | Recommendation | Groq llama-3.3-70b | Natural language answer |
| 8 | Evaluation | DeepEval + LLM Judge | Grade answer quality |

---

## 🤖 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **LLM** | Groq (llama-3.3-70b) | Fast inference, free tier |
| **LLM Fallback** | Template Provider | Offline, deterministic |
| **Retrieval** | BM25 + Plain-text fallback | Keyword search, no GPU |
| **Vector DB** | ChromaDB | Semantic search (Linux/Mac) |
| **RAG** | Custom pipeline | Grounded, evidence-based answers |
| **Agents** | Custom sequential | Auditable, deterministic |
| **Session Memory** | LangGraph + MemorySaver | Multi-turn conversation |
| **LLM Orchestration** | LangChain | Unified LLM abstraction |
| **Evaluation** | DeepEval + LLM Judge | Faithfulness, relevancy scoring |
| **Backend** | FastAPI + uvicorn | Async API, auto Swagger docs |
| **Frontend** | React 18 + Vite | 13-page dashboard |
| **Charts** | Recharts | Heatmap, timeline, telemetry |
| **Tracing** | LangSmith (optional) | Production observability |

---

## 📱 Frontend Pages (13)

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Grid health score, heatmap, timeline, predictions |
| Query Console | `/query` | Natural language Q&A with agent trace |
| ETL | `/etl` | Upload CSVs, ingest data, validate retrieval |
| Grid Stability | `/stability` | Voltage/frequency/stability trends |
| Failure Analysis | `/failure` | Root causes with probability scores |
| Smart Meter | `/meter` | Household power consumption patterns |
| Telemetry | `/telemetry` | Raw sensor time-series (last 100 readings) |
| Recommendations | `/recommendations` | History of AI-generated recommendations |
| Agent Flow | `/agents` | Multi-agent pipeline visualization |
| Incident Timeline | `/timeline` | Chronological incident view |
| Heatmap Analytics | `/heatmap` | Region × Severity matrix |
| Predictive AI | `/predict` | Composite failure risk per region |
| Settings / Admin | `/settings` | LLM provider, index management |

---

## 🗂️ Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── core/
│   │   ├── config.py        # Settings from .env
│   │   ├── lifespan.py      # Startup/shutdown
│   │   ├── llm_router.py    # LLM fallback chain
│   │   └── logging.py       # Structured logging
│   ├── agents/
│   │   ├── orchestrator.py  # 5-agent sequential pipeline
│   │   ├── retrieval_agent.py
│   │   ├── stability_agent.py
│   │   ├── failure_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── escalation_agent.py  # A2A conditional escalation
│   │   └── graph.py         # LangGraph StateGraph (chat endpoint)
│   ├── rag/
│   │   ├── hybrid_retriever.py  # BM25 + text fallback + CRAG
│   │   ├── bm25_index.py
│   │   ├── embeddings.py    # Hash embedder (no torch required)
│   │   ├── llm.py           # Groq/OpenAI/Template providers
│   │   └── vector_store.py  # ChromaDB wrapper
│   ├── api/
│   │   ├── routes_analyze.py    # POST /analyze (main query)
│   │   ├── routes_chat.py       # POST /chat/query (LangGraph)
│   │   ├── routes_datasets.py   # ETL pipeline
│   │   ├── routes_analytics.py  # Dashboard data
│   │   ├── routes_predict.py    # Predictive AI
│   │   └── routes_eval.py       # DeepEval evaluation
│   ├── cache/
│   │   └── semantic_cache.py    # Cosine similarity cache
│   ├── data/
│   │   ├── ingestion_pipeline.py
│   │   ├── loader.py
│   │   ├── normalizer.py
│   │   ├── cleaner.py
│   │   └── aggregator.py
│   ├── evaluation/
│   │   ├── deepeval_runner.py
│   │   ├── llm_judge.py
│   │   └── metrics.py       # Heuristic fallback
│   └── services/
│       ├── analytics_service.py
│       ├── event_bus.py
│       └── feedback_store.py
├── datasets/                # Raw CSV files
├── data_processed/          # chunks.jsonl, bm25_index.pkl
├── requirements.txt
├── requirements-ml.txt
└── .env                     # API keys (not committed)

frontend/
├── src/
│   ├── App.jsx              # Router (13 pages)
│   ├── pages/               # All 13 page components
│   ├── components/          # Charts, cards, layout
│   └── services/api.js      # Axios client + interceptors
└── vite.config.js           # Proxy to backend:8000
```

---

## ⚙️ Configuration (.env)

```env
# LLM Provider (groq recommended — fastest, free tier)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Optional fallbacks
OPENAI_API_KEY=
GEMINI_API_KEY=

# Paths
DATA_DIR=./datasets
CHROMA_PERSIST_DIR=../chroma_store

# Embedding model (hash = no torch required, works on all platforms)
EMBEDDING_MODEL=hash

# Optional LangSmith tracing
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Main query → 5-agent pipeline |
| POST | `/api/v1/chat/query` | LangGraph multi-turn chat |
| GET | `/api/v1/health` | System health + component status |
| POST | `/api/v1/datasets/{file}/process` | ETL ingest |
| GET | `/api/v1/datasets` | List available datasets |
| GET | `/api/v1/grid-score` | Overall grid health score |
| GET | `/api/v1/heatmap` | Region × severity matrix |
| GET | `/api/v1/timeline` | Incident timeline |
| GET | `/api/v1/predict` | Predictive failure intelligence |
| POST | `/api/v1/evaluate` | DeepEval + LLM Judge scoring |
| GET | `/api/v1/incidents` | Incident browse |
| GET | `/docs` | Swagger UI (auto-generated) |

---

## 🛡️ Guardrails

Input validation before any processing:
- **PII blocking** — SSN, credit cards, passports, API keys
- **PII masking** — email, phone, IP address (query still processed)
- **Injection detection** — "ignore previous instructions" patterns
- **Topic filtering** — off-topic queries redirected
- **Greeting pass-through** — "hi", "hello", "help" allowed through

---

## 📊 Evaluation Framework

Every AI response can be scored on demand:

| Metric | Tool | Measures |
|--------|------|---------|
| Faithfulness | DeepEval | Did answer contradict retrieved evidence? |
| Answer Relevancy | DeepEval | Did answer address the question? |
| Accuracy | LLM Judge (Groq) | Factual grounding in evidence |
| Completeness | LLM Judge | Covers causes, recommendations, reasoning |
| Actionability | LLM Judge | Practical operational steps |
| Format | Heuristic | Schema correctness |

All metrics fall back to deterministic heuristic scoring when LLM API is unavailable.

---

## 🔄 Fallback Architecture

```
LLM: Groq → OpenAI → Anthropic → Template (offline)
Search: BM25 → Plain-text keyword match → Empty
Storage: ChromaDB → chunks.jsonl (JSONL always works)
Evaluation: DeepEval → Heuristic scorer
```

---

## 📋 Datasets

| File | Records | Description |
|------|---------|-------------|
| `smart_grid_stability_augmented.csv` | 100 rows | Grid stability with voltage, frequency, stability scores |
| `household_power_consumption.csv` | 2M rows | Household-level power consumption |
| `electric_power_consumption.csv` | 2M rows | Electric grid consumption data |

---

## ⚠️ Known Limitations

| Limitation | Reason | Production Fix |
|-----------|--------|---------------|
| ChromaDB disabled on Windows/Python 3.13 | Crash bug in v1.5.9 | Upgrade ChromaDB or deploy on Linux |
| BM25 startup warning | Pickle version mismatch on first run | Run ETL once to rebuild locally |
| Groq API needs internet | Corporate firewall may block api.groq.com | Use local Ollama or whitelist the domain |
| JSONL history storage | Demo simplicity | Replace with PostgreSQL + 90-day retention |
| In-memory semantic cache | Lost on restart | Replace with Redis |

---

## 🎯 Demo Script

1. **Start backend:** `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio`
2. **Start frontend:** `npm run dev`
3. **ETL tab** → Select `smart_grid_stability_augmented.csv` → Click **Ingest**
4. **Query Console** → Ask: *"Voltage instability in South Zone during peak demand. What are the causes?"*
5. **Click "Run evaluation"** to see DeepEval scores
6. **Show Predictive AI tab** for proactive failure detection

---

## 👥 Team

Capstone Project — AI-Powered Smart Grid Energy Intelligence Assistant

---

*Built with FastAPI, React, LangChain, LangGraph, Groq, DeepEval, BM25, ChromaDB*
