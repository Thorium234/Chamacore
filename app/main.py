"""ChamaCore FastAPI application entrypoint."""

import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import (
    REQUEST_ID_HEADER,
    configure_logging,
    reset_request_id,
    set_request_id,
)
from app.core.metrics import REGISTRY, request_metrics_middleware
from app.db.session import get_db

settings = get_settings()
configure_logging(debug=settings.debug)

app = FastAPI(title=settings.app_name, version="1.0.0")

logger = logging.getLogger("app.request")


def _request_client_host(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


# CORS for the browser frontend (report 2026-09-17, production readiness:
# explicit origins, never "*"). Ajex web origins configuration is driven by
# CHAMACORE_CORS_ORIGINS. Provider webhooks (Daraja STK/C2B) are server-to-
# server and are not affected by browser same-origin policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
    expose_headers=[REQUEST_ID_HEADER],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "request rejected",
        extra={
            "code": exc.code,
            "status": exc.status_code,
            "path": request.url.path,
            "client": _request_client_host(request),
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.middleware("http")
async def _record_request_metrics(request: Request, call_next):
    return await request_metrics_middleware(request, call_next)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    token = set_request_id(request_id)
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": _request_client_host(request),
            },
        )
        raise
    else:
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request complete",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "client": _request_client_host(request),
            },
        )
        return response
    finally:
        reset_request_id(token)


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": app.version, "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    """Prometheus text exposition of process-level HTTP metrics."""
    return PlainTextResponse(
        REGISTRY.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )