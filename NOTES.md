# Project Notes — Smart Grid AI Assistant (FDE Capstone)

## Status: In Progress

Reference project: `D:\FDE\capstone\AI-Powered-Smart-Grid-Energy-Intelligence-Assistant` (colleague's working version)

---

## Changes Made (2026-06-02)

Ported key components from the working reference project.

### New files added
| File | Purpose |
|------|---------|
| `backend/app/agents/_common.py` | `node_span` / `truncate_context` shared utilities |
| `backend/app/agents/graph.py` | **LangGraph StateGraph + MemorySaver** (CRITICAL: MemorySaver not SqliteSaver — broke in 0.2.50+) |
| `backend/app/agents/grid_retrieval.py` | LangGraph retrieval node |
| `backend/app/agents/stability.py` | LangGraph stability analysis node |
| `backend/app/agents/failure_analysis.py` | LangGraph root-cause node |
| `backend/app/agents/recommendation.py` | LangGraph recommendation + synthesis nodes |
| `backend/app/cache/__init__.py` + `semantic_cache.py` | Cosine-similarity cache (skips LLM on repeated queries) |
| `backend/app/services/event_bus.py` | In-process agent telemetry bus |
| `backend/app/services/feedback_store.py` | Thumbs-up/down persistence (JSONL) |
| `backend/app/core/llm_router.py` | LLM fallback chain: Groq → OpenAI → Anthropic → Gemini |
| `backend/app/api/routes_chat.py` | `POST /api/v1/chat/query` (LangGraph), `POST /api/v1/chat/feedback` |

### Files modified
| File | Change |
|------|--------|
| `backend/app/rag/hybrid_retriever.py` | Added CRAG (query reformulation when top score < `crag_relevance_threshold`) |
| `backend/app/core/config.py` | Added `groq_model_large/small`, `llm_fallback_chain`, `crag_relevance_threshold`, `semantic_cache_threshold/max_items`, `langchain_tracing_v2/api_key/endpoint/project`, `openai_base_url`, `fastembed_model` |
| `backend/app/core/lifespan.py` | LangSmith tracing at startup; LLM status now includes Groq + Gemini |
| `backend/app/main.py` | `routes_chat` imported and registered at `/api/v1/chat/*` |
| `backend/app/models/schemas.py` | Added `ChatRequest`, `ChatResponse`, `FeedbackRequest` |
| `backend/requirements-ml.txt` | Added `langgraph>=0.2.50`, `langgraph-checkpoint-sqlite>=2.0.0`, `langchain-groq>=0.3.0`, `langsmith>=0.2.0`, `fastembed>=0.3.0`, `tenacity>=8.2.3`, bumped langchain to `>=0.3.20` |

---

## Architecture

Two parallel query paths, same retrieval + LLM stack:

1. **`POST /api/v1/analyze`** — Sequential `AgentOrchestrator` (existing, envelope pattern)
2. **`POST /api/v1/chat/query`** — LangGraph `StateGraph` + `MemorySaver` (new, session-aware)

This project's default LLM is **Groq** (`llm_provider=groq`, `groq_model=llama-3.3-70b-versatile`).
The `llm_router` fallback chain: `groq_large → openai → groq_small → anthropic`.

---

## Next Steps

1. `pip install -r requirements-ml.txt`
2. Add `.env`: `GROQ_API_KEY=gsk_...` (primary) and/or `OPENAI_API_KEY=sk_...`
3. Run ingestion: `POST /api/v1/ingest` → `POST /api/v1/embed`
4. Test: `POST /api/v1/analyze` and `POST /api/v1/chat/query`
5. Enable CRAG: `CRAG_RELEVANCE_THRESHOLD=0.6` in `.env`
6. Enable LangSmith: `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY=...`
