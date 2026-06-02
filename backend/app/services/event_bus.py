"""In-process event bus for agent telemetry."""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from typing import Any, Dict, List

_local = threading.local()


def current_session_id() -> str:
    sid = getattr(_local, "session_id", None)
    if sid is None:
        sid = str(uuid.uuid4())
        _local.session_id = sid
    return sid


def set_session_id(sid: str) -> None:
    _local.session_id = sid


class EventBus:
    def __init__(self) -> None:
        self._store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock  = threading.Lock()

    def emit(self, event_type: str, session_id: str | None = None, **payload) -> None:
        sid = session_id or current_session_id()
        with self._lock:
            self._store[sid].append({"type": event_type, **payload})

    def drain(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return self._store.pop(session_id, [])

    def peek(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._store.get(session_id, []))


event_bus = EventBus()
