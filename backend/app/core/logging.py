"""
Structured JSON logging — Windows / uvicorn-safe.

Why this version
----------------
The previous implementation removed ALL root logger handlers and silenced
uvicorn.access + uvicorn.error. On some Windows + asyncio + chromadb setups,
that caused uvicorn to silently exit after lifespan startup_complete because
its own startup logger couldn't find a propagation path.

Fix: leave uvicorn's loggers ALONE. Just add a JSON formatter to whatever
handlers root has, without removing anything. Uvicorn's own "Application
startup complete" + "Uvicorn running on ..." lines now print normally.

Result: app logs are still structured JSON, uvicorn logs are visible in
plain text — the demo shows both clearly.
"""
import logging
import sys
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
    _JSON_AVAILABLE = True
except Exception:  # noqa: BLE001
    _JSON_AVAILABLE = False


def configure_logging(level: str = "INFO") -> None:
    """
    Add a JSON-formatted stdout handler to the root logger. Do NOT remove
    uvicorn handlers — that's what was killing the server.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Add ONE JSON handler if we haven't already (idempotent across reloads).
    already_have_json = any(
        getattr(h, "_smartgrid_json", False) for h in root.handlers
    )
    if not already_have_json and _JSON_AVAILABLE:
        handler = logging.StreamHandler(sys.stdout)
        fmt = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
        handler.setFormatter(fmt)
        handler._smartgrid_json = True  # marker for idempotency
        root.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "smartgrid")
