"""
FastAPI lifespan — minimal, Windows-safe, NO Chroma warm-up.

Why this version
----------------
The previous lifespan attempted to pre-warm ChromaDB at startup. On
Python 3.11 + Windows + ChromaDB 1.5.9, that interaction killed uvicorn
silently right after `startup_complete` — no traceback, no error log,
just the server process exiting.

Fix: do ONLY safe, synchronous work at startup:
  - load BM25 cache (pure pickle, deterministic)
  - load QA history (pure JSONL, deterministic)
  - load ETL history (pure JSONL, deterministic)
  - report component statuses
  - NO ChromaDB calls

ChromaDB is lazy-opened on the FIRST `/embed` request, where the FastAPI
exception handlers catch errors cleanly without bringing down the server.
This makes the first `/embed` ~5s slower but uvicorn never crashes.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _try_build_bm25(app: FastAPI) -> None:
    """Best-effort BM25 build. Never raises."""
    try:
        from app.rag.bm25_index import BM25Index, build_bm25_index
    except Exception as exc:  # noqa: BLE001
        logger.info("bm25_import_skipped", extra={"err": str(exc)})
        app.state.components["bm25"] = "not_installed"
        return

    cache_path = Path("./data_processed/bm25_index.pkl")
    chunks_path = Path("./data_processed/chunks.jsonl")

    if cache_path.exists():
        try:
            app.state.bm25_index = BM25Index.load(cache_path)
            app.state.components["bm25"] = "ok"
            logger.info(
                "bm25_loaded_from_cache",
                extra={"path": str(cache_path),
                       "n_docs": len(app.state.bm25_index.chunk_ids)},
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("bm25_cache_load_failed", extra={"err": str(exc)})
            # Delete stale pkl (often a Python-version pickle mismatch) so
            # the rebuild-from-jsonl path runs cleanly on next attempt.
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                pass

    if not chunks_path.exists():
        app.state.components["bm25"] = "no_chunks"
        return

    try:
        rows = []
        with chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().strip("\x00")
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        idx = build_bm25_index(rows)
        idx.save(cache_path)
        app.state.bm25_index = idx
        app.state.components["bm25"] = "ok"
        logger.info("bm25_built_at_boot", extra={"n_docs": len(idx.chunk_ids)})
    except Exception as exc:  # noqa: BLE001
        logger.warning("bm25_build_failed", extra={"err": str(exc)})
        app.state.components["bm25"] = "error"



def _auto_ingest_if_empty() -> None:
    """Demo-readiness: if chunks.jsonl is missing or empty at startup, run the
    ingestion pipeline automatically from the datasets/ folder so every tab has
    data immediately — no manual ETL click required."""
    chunks_path = Path("./data_processed/chunks.jsonl")
    try:
        valid = 0
        if chunks_path.exists():
            with chunks_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().strip("\x00"):
                        valid += 1
                        if valid >= 1:
                            break
        if valid == 0:
            logger.info("auto_ingest_begin", extra={"reason": "chunks_missing_or_empty"})
            from app.data.ingestion_pipeline import run_ingestion
            report = run_ingestion()
            logger.info("auto_ingest_done",
                        extra={"chunks": report.chunks_written, "errors": report.errors[:2]})
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto_ingest_failed", extra={"err": str(exc)})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan handler: runs startup tasks before ``yield`` and teardown after.

    Startup sequence (intentionally minimal and Windows-safe):
      1. Optionally enable LangSmith tracing via environment variables.
      2. Detect which LLM API keys are present and record component statuses.
      3. Auto-ingest datasets if no processed chunks exist yet (demo readiness).
      4. Load the BM25 index from cache or rebuild it from ``chunks.jsonl``.
      5. Restore QA history and ETL run history from JSONL files.

    ChromaDB is deliberately NOT touched here — see the module docstring.
    """
    import os
    settings = get_settings()

    # ---- LangSmith tracing (optional) ----
    if getattr(settings, "langchain_tracing_v2", False) and getattr(settings, "langchain_api_key", ""):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"]   = getattr(settings, "langchain_endpoint", "https://api.smith.langchain.com")
        os.environ["LANGCHAIN_API_KEY"]    = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"]    = getattr(settings, "langchain_project", "smart-grid-energy-assistant")
        logger.info("langsmith_tracing_enabled",
                    extra={"project": getattr(settings, "langchain_project", "")})
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)

    logger.info(
        "startup_begin",
        extra={
            "app_env": settings.app_env,
            "data_dir": settings.data_dir,
            "chroma_persist_dir": settings.chroma_persist_dir,
            "multi_tenancy_enabled": settings.multi_tenancy_enabled,
            "llm_provider": settings.llm_provider,
        },
    )

    # Detect which LLM keys are actually available
    _has_groq      = bool(getattr(settings, "groq_api_key", ""))
    _has_openai    = bool(getattr(settings, "openai_api_key", ""))
    _has_anthropic = bool(getattr(settings, "anthropic_api_key", ""))
    _has_gemini    = bool(getattr(settings, "gemini_api_key", ""))
    _llm_status    = "configured" if any([_has_groq, _has_openai, _has_anthropic, _has_gemini]) else "fallback_template"

    app.state.components = {
        "api": "ok",
        "config": "ok",
        "logging": "ok",
        "ingestion": "not_run",
        "chroma": "not_initialized",   # lazy — opens on first /embed
        "embeddings": "not_initialized",
        "bm25": "not_initialized",
        "llm": _llm_status,
        "auth": "enabled" if settings.multi_tenancy_enabled else "disabled",
    }
    app.state.settings = settings
    app.state.bm25_index = None

    # ---- Auto-ingest if no processed data yet (demo readiness) ----
    _auto_ingest_if_empty()

    # ---- BM25 (safe, pure-Python) ----
    _try_build_bm25(app)

    # ---- QA history (safe, JSONL only) ----
    try:
        from app.services.analytics_service import load_history
        n = load_history()
        app.state.components["qa_history"] = f"ok ({n} loaded)" if n else "empty"
    except Exception as exc:  # noqa: BLE001
        logger.warning("qa_history_init_failed", extra={"err": str(exc)})
        app.state.components["qa_history"] = "error"

    # ---- ETL history (safe, JSONL only) ----
    try:
        from app.services import etl_history
        n_etl = etl_history.load_history()
        last = etl_history.last_run()
        app.state.components["etl_history"] = (
            f"ok ({n_etl} runs)" if last else "empty"
        )
        if last:
            app.state.components["ingestion"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("etl_history_init_failed", extra={"err": str(exc)})
        app.state.components["etl_history"] = "error"

    # NOTE: NO Chroma warm-up — see file docstring for the reason.
    logger.info("startup_complete", extra={"components": app.state.components})

    yield

    logger.info("shutdown_complete")
