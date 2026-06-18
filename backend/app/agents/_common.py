"""Shared utilities for all agents (LangGraph nodes + custom agents)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from app.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def node_span(name: str) -> Generator[None, None, None]:
    """Context manager that logs entry/exit for a named LangGraph node and re-raises any exception."""
    logger.info(f"[{name}] → start")
    try:
        yield
    except Exception as e:
        logger.error(f"[{name}] error: {e!r}")
        raise
    finally:
        logger.info(f"[{name}] ← done")


def truncate_context(text: str, max_chars: int = 12000) -> str:
    """Clip `text` to `max_chars` characters and append a truncation marker if clipping occurred."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"
