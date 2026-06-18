"""Feedback store — persists user thumbs-up/down ratings to JSONL."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.core.logging import get_logger

logger = get_logger(__name__)

_PATH = Path("./data_processed/feedback.jsonl")


class FeedbackStore:
    """Persists user rating events (thumbs up/down) to a JSONL file and an in-memory list."""

    def __init__(self) -> None:
        """Initialize the store and load any existing ratings from disk."""
        self._lock    = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Read existing feedback entries from the JSONL file into memory."""
        if not _PATH.exists():
            return
        try:
            with _PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._entries.append(json.loads(line))
        except Exception as exc:
            logger.warning("feedback_load_failed", extra={"err": str(exc)})

    def save(self, session_id: str, message_id: str, rating: int, comment: str = "") -> None:
        """Record a new rating, appending it to both memory and the JSONL file."""
        import time
        entry = {"session_id": session_id, "message_id": message_id,
                 "rating": rating, "comment": comment, "ts": time.time()}
        with self._lock:
            self._entries.append(entry)
            try:
                _PATH.parent.mkdir(parents=True, exist_ok=True)
                with _PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as exc:
                logger.warning("feedback_persist_failed", extra={"err": str(exc)})

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent `limit` feedback entries, newest first."""
        with self._lock:
            return list(reversed(self._entries[-limit:]))

    def stats(self) -> Dict[str, Any]:
        """Return aggregate counts of total, positive, and negative ratings."""
        with self._lock:
            total = len(self._entries)
            pos   = sum(1 for e in self._entries if e.get("rating", 0) > 0)
            neg   = sum(1 for e in self._entries if e.get("rating", 0) < 0)
        return {"total": total, "positive": pos, "negative": neg}


feedback_store = FeedbackStore()
