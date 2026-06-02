"""
Smart Grid AI Assistant - FastAPI entrypoint.

Run (dev):  uvicorn app.main:app --reload --port 8000
Run (prod): uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import (
    routes_admin,
    routes_analytics,
    routes_analyze,
    routes_auth,
    routes_chat,
    routes_datasets,
    routes_embed,
    routes_eval,
    routes_health,
    routes_incidents,
    routes_ingest,
    routes_pdf,
    routes_predict,
    routes_validate,
    routes_ws,
)
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.app_log_level)
    logger = get_logger(__name__)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="AI-powered smart grid energy intelligence assistant.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = req_id
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("unhandled_error", extra={"request_id": req_id})
            return JSONResponse(
                status_code=500,
                content={"detail": "internal_server_error", "request_id": req_id},
            )
        response.headers["x-request-id"] = req_id
        return response

    app.include_router(routes_health.router)
    app.include_router(routes_health.router,    prefix="/api/v1")
    app.include_router(routes_ingest.router,    prefix="/api/v1")
    app.include_router(routes_validate.router,  prefix="/api/v1")
    app.include_router(routes_embed.router,     prefix="/api/v1")
    app.include_router(routes_auth.router,      prefix="/api/v1")
    app.include_router(routes_incidents.router, prefix="/api/v1")
    app.include_router(routes_analyze.router,   prefix="/api/v1")
    app.include_router(routes_chat.router,      prefix="/api/v1")
    app.include_router(routes_analytics.router, prefix="/api/v1")
    app.include_router(routes_admin.router,     prefix="/api/v1")
    app.include_router(routes_datasets.router,  prefix="/api/v1")
    app.include_router(routes_eval.router,      prefix="/api/v1")
    app.include_router(routes_predict.router,   prefix="/api/v1")
    app.include_router(routes_pdf.router,       prefix="/api/v1")
    app.include_router(routes_ws.router,        prefix="/api/v1")

    logger.info("app_initialized", extra={"env": settings.app_env, "version": __version__})
    return app


app = create_app()
