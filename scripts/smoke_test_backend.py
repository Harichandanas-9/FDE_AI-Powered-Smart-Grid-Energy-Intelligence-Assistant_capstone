"""
Smoke test for the backend.

Boots the FastAPI app in-process (no uvicorn needed) and hits /health.
Use this to quickly verify the backend is healthy without running a server.

    cd backend
    python ../scripts/smoke_test_backend.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make `app` importable when running from project root
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from httpx import AsyncClient, ASGITransport  # noqa: E402
from app.main import app  # noqa: E402


async def main() -> int:
    print("[smoke] booting app in-process...")
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/v1/health")
            print(f"[smoke] GET /api/v1/health -> {r.status_code}")
            print(f"[smoke] body: {r.json()}")
            assert r.status_code == 200, "health check failed"

            r2 = await client.get("/")
            print(f"[smoke] GET / -> {r2.status_code} {r2.json()}")
            assert r2.status_code == 200, "root failed"

    print("[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
