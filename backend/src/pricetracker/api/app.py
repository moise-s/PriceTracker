"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pricetracker import __version__
from pricetracker.api.routes import admin, alerts, auth, catalog, lists, profile, runs, system
from pricetracker.db.session import init_engine
from pricetracker.logs import bind, configure_logging, log_event
from pricetracker.services.errors import ServiceError
from pricetracker.settings import get_settings

logger = logging.getLogger("pricetracker.api")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    init_engine(settings)
    app = FastAPI(
        title="PriceTracker API",
        version=__version__,
        description="Comparação de preços de supermercado com cobertura, frescor e custo de deslocamento.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        bind(request_id=request_id, run_id=None, target_id=None, market=None)
        started = time.monotonic()
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-Id"] = request_id
        if request.url.path not in ("/api/v1/health/live", "/api/v1/health/ready"):
            log_event(
                logger,
                logging.INFO,
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return response

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        headers = {}
        if (
            exc.status_code == 429
            and isinstance(exc.details, dict)
            and exc.details.get("retry_after_seconds")
        ):
            headers["Retry-After"] = str(exc.details["retry_after_seconds"])
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_failed",
                "message": "Dados inválidos.",
                "details": details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": "http_error", "message": str(exc.detail), "details": None},
        )

    prefix = "/api/v1"
    for router in (
        system.router,
        auth.router,
        catalog.router,
        lists.router,
        profile.router,
        runs.router,
        alerts.router,
        admin.router,
    ):
        app.include_router(router, prefix=prefix)
    return app
