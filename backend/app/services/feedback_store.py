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
    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
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
        with self._lock:
            return list(reversed(self._entries[-limit:]))

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            pos   = sum(1 for e in self._entries if e.get("rating", 0) > 0)
            neg   = sum(1 for e in self._entries if e.get("rating", 0) < 0)
        return {"total": total, "positive": pos, "negative": neg}


feedback_store = FeedbackStore()
