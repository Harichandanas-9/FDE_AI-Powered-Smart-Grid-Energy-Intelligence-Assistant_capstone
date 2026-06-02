"""LLM router — fallback chain with per-provider timeout and max_retries=1.

Fast-fail design: each provider gets 15 s max, 1 retry max.
Default chain: groq_large only (fastest). Extend via LLM_FALLBACK_CHAIN env var.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, List

from langchain_core.messages import BaseMessage

from app.core.logging import get_logger

logger = get_logger(__name__)

LLM_TIMEOUT    = 10   # seconds per provider call
LLM_MAX_RETRIES = 0   # langchain retries per provider (0 = no retry, 1 = one retry)


class TaskType(str, Enum):
    ROUTING       = "routing"
    ANALYSIS      = "analysis"
    GENERATION    = "generation"
    SUMMARIZATION = "summarization"


def _build_groq(settings, size: str = "large"):
    api_key = getattr(settings, "groq_api_key", "").strip()
    if not api_key:
        return None
    try:
        from langchain_groq import ChatGroq
        model = (getattr(settings, "groq_model_large", "llama-3.3-70b-versatile")
                 if size == "large"
                 else getattr(settings, "groq_model_small", "llama-3.1-8b-instant"))
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=0,
            max_retries=LLM_MAX_RETRIES,
            timeout=LLM_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("groq_build_failed", extra={"err": str(exc), "size": size})
        return None


def _build_openai(settings):
    if not getattr(settings, "openai_api_key", "").strip():
        return None
    try:
        from langchain_openai import ChatOpenAI
        kw: dict = dict(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0,
            max_retries=LLM_MAX_RETRIES,
            timeout=LLM_TIMEOUT,
        )
        if getattr(settings, "openai_base_url", ""):
            kw["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kw)
    except Exception as exc:
        logger.warning("openai_build_failed", extra={"err": str(exc)})
        return None


def _build_anthropic(settings):
    if not getattr(settings, "anthropic_api_key", "").strip():
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=0,
            timeout=LLM_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
        )
    except Exception as exc:
        logger.warning("anthropic_build_failed", extra={"err": str(exc)})
        return None


def _build_gemini(settings):
    api_key = getattr(settings, "gemini_api_key", "").strip()
    if not api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=getattr(settings, "gemini_model", "gemini-1.5-flash"),
            google_api_key=api_key,
            temperature=0,
        )
    except Exception as exc:
        logger.warning("gemini_build_failed", extra={"err": str(exc)})
        return None


class _LLMRouter:
    def __init__(self) -> None:
        self._llms: dict = {}

    def _providers(self):
        try:
            from app.core.config import get_settings
            s = get_settings()
        except Exception:
            return []

        # Use only configured providers — skip any with missing API keys immediately.
        chain_str = getattr(s, "llm_fallback_chain", "groq_large")
        chain     = [x.strip() for x in chain_str.split(",") if x.strip()]

        builders = {
            "groq_large":  lambda: _build_groq(s, "large"),
            "groq_small":  lambda: _build_groq(s, "small"),
            "groq":        lambda: _build_groq(s, "large"),
            "openai":      lambda: _build_openai(s),
            "openai_mini": lambda: _build_openai(s),
            "anthropic":   lambda: _build_anthropic(s),
            "gemini":      lambda: _build_gemini(s),
        }

        providers = []
        for name in chain:
            if name not in self._llms:
                factory = builders.get(name)
                self._llms[name] = factory() if factory else None
            if self._llms[name] is not None:
                providers.append((name, self._llms[name]))
        return providers

    def invoke(self, task: TaskType, messages: List[BaseMessage], **kw) -> Any:
        last_err = None
        for name, llm in self._providers():
            try:
                result = llm.invoke(messages, **kw)
                logger.info(f"[llm_router] provider={name} task={task.value}")
                return result
            except Exception as exc:
                logger.warning(f"[llm_router] {name} failed: {exc!r} — trying next")
                last_err = exc
        raise RuntimeError(
            f"All LLM providers exhausted for task={task.value}. Last error: {last_err}"
        )

    async def ainvoke(self, task: TaskType, messages: List[BaseMessage], **kw) -> Any:
        last_err = None
        for name, llm in self._providers():
            try:
                result = await llm.ainvoke(messages, **kw)
                logger.info(f"[llm_router] async provider={name} task={task.value}")
                return result
            except Exception as exc:
                logger.warning(f"[llm_router] async {name} failed: {exc!r}")
                last_err = exc
        raise RuntimeError(
            f"All LLM providers exhausted (async) task={task.value}. Last error: {last_err}"
        )


router = _LLMRouter()
