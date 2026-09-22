"""ChamaCore FastAPI application entrypoint."""

import hmac
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
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

logger = logging.getLogger("app.request")


def _request_client_host(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _make_app(*, debug: bool) -> FastAPI:
    """Build a complete application instance.

    Interactive docs (Swagger UI/ReDoc) and the raw OpenAPI JSON are only
    wired up in debug builds; production exposes no API schema discovery
    endpoint (production-readiness brief 3.2). Production builds also get a
    minimal security-headers middleware as defense in depth (brief 3.5); the
    reference deployment keeps the reverse proxy as the primary header source.
    """
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
        openapi_url="/openapi.json" if debug else None,
    )

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

    if not debug:
        @app.middleware("http")
        async def _security_headers_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
            return response

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
        payload: dict[str, str] = {"service": settings.app_name, "version": app.version}
        if settings.debug:
            payload["docs"] = "/docs"
        return payload

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(db: Session = Depends(get_db)) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics(request: Request) -> PlainTextResponse:
        """Prometheus text exposition of process-level HTTP metrics.

        Protected in production (production-readiness brief 3.3): the endpoint
        is only reachable with the configured CHAMACORE_METRICS_TOKEN via the
        X-Metrics-Token header, and responds 404 when the token is unset or the
        header is missing/wrong. Debug builds keep the endpoint open.
        """
        if not settings.debug:
            expected = settings.metrics_token
            provided = request.headers.get("X-Metrics-Token")
            if (
                not expected
                or provided is None
                or not hmac.compare_digest(provided, expected)
            ):
                raise HTTPException(status_code=404, detail="Not found")
        return PlainTextResponse(
            REGISTRY.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = _make_app(debug=settings.debug)