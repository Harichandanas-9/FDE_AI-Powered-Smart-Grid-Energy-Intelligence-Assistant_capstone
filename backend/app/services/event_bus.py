"""In-process event bus for agent telemetry."""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from typing import Any, Dict, List

_local = threading.local()


def current_session_id() -> str:
    """Return the session ID for the current thread, generating one if not yet set."""
    sid = getattr(_local, "session_id", None)
    if sid is None:
        sid = str(uuid.uuid4())
        _local.session_id = sid
    return sid


def set_session_id(sid: str) -> None:
    """Bind a specific session ID to the current thread."""
    _local.session_id = sid


class EventBus:
    """Thread-safe, in-memory pub/sub bus keyed by session ID.

    Agents emit events; the API handler drains them to include in the response trace.
    """

    def __init__(self) -> None:
        """Initialize empty event store and threading lock."""
        self._store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock  = threading.Lock()

    def emit(self, event_type: str, session_id: str | None = None, **payload) -> None:
        """Append an event to the session's event queue."""
        sid = session_id or current_session_id()
        with self._lock:
            self._store[sid].append({"type": event_type, **payload})

    def drain(self, session_id: str) -> List[Dict[str, Any]]:
        """Remove and return all events for the given session."""
        with self._lock:
            return self._store.pop(session_id, [])

    def peek(self, session_id: str) -> List[Dict[str, Any]]:
        """Return a copy of the event queue for the given session without removing it."""
        with self._lock:
            return list(self._store.get(session_id, []))


event_bus = EventBus()
