"""
WebSocket telemetry stream.

  GET /api/v1/ws/telemetry?mode=auto&rate=1.0

mode  : replay | synthetic | auto (default: auto = replay if data exists, else synth)
rate  : ticks per second (default 1.0 — clamped to 0.1..10)

Auth note: WebSocket auth in FastAPI is connection-time only. When
MULTI_TENANCY_ENABLED=true, the client should pass ?token=<jwt>; otherwise the
endpoint accepts anonymous connections (matches the rest of the project's
"off by default" multi-tenancy posture).
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.auth import decode_token
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.stream_service import stream_telemetry

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/telemetry")
async def ws_telemetry(
    ws: WebSocket,
    mode: str = Query(default="auto", pattern="^(auto|replay|synthetic)$"),
    rate: float = Query(default=1.0, ge=0.1, le=10.0),
    token: Optional[str] = Query(default=None),
):
    """Stream telemetry ticks over a WebSocket at the requested rate.

    In multi-tenancy mode a valid JWT is required; in single-tenant mode the token
    is optional and decoded best-effort to capture tenant context. Each JSON tick
    is annotated with the resolved tenant_id before being sent.
    """
    settings = get_settings()

    # ---- Optional JWT check ----
    tenant_id = "default"
    if settings.multi_tenancy_enabled:
        if not token:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            payload = decode_token(token, settings=settings)
            tenant_id = payload.get("tenant_id", "default")
        except ValueError:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    elif token:
        # token optional in single-tenant mode; decode best-effort
        try:
            payload = decode_token(token, settings=settings)
            tenant_id = payload.get("tenant_id", "default")
        except ValueError:
            pass

    await ws.accept()
    logger.info("ws_connected", extra={"mode": mode, "rate": rate, "tenant_id": tenant_id})

    interval = 1.0 / rate
    try:
        async for tick in stream_telemetry(mode=mode, interval_sec=interval):
            tick["tenant_id"] = tenant_id
            await ws.send_text(json.dumps(tick, default=str))
    except WebSocketDisconnect:
        logger.info("ws_disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.exception("ws_stream_error", extra={"err": str(exc)})
        try: await ws.close()
        except Exception: pass
