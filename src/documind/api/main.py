"""FastAPI application factory for DocuMind.

Entrypoint: ``documind.api.main:app``

The ``create_app()`` factory wires up:
    - OTEL auto-instrumentation (App Insights export)
    - CORS middleware
    - Global exception handlers (structured JSON errors)
    - Lifespan hooks (startup/shutdown)
    - All API routers
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from documind.core.config.settings import settings
from documind.core.tracing import configure_telemetry

# Configure root logger so all documind.* loggers are visible in the console.
# force=True is required because uvicorn configures the root logger before
# importing the app, which makes a plain basicConfig() a silent no-op.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    force=True,
)

# Silence noisy Azure SDK / OTEL loggers (keep only warnings+)
for _noisy in ("azure", "azure.core", "azure.monitor", "azure.identity",
               "azure.cosmos", "azure.cosmos.aio",
               "opentelemetry", "urllib3", "httpcore", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
# Cosmos SDK diagnostic logger is extremely verbose
logging.getLogger("azure.cosmos._cosmos_client_connection").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos.cosmos_client").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks.

    Startup:
        - Configure OTEL telemetry → App Insights
        - Instrument FastAPI with opentelemetry-instrumentation-fastapi
    Shutdown:
        - Flush telemetry
    """
    # ── Startup ─────────────────────────────────────────────────
    configure_telemetry(service_name="documind-api")

    # Wire FastAPI auto-instrumentation (creates spans per request)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OTEL auto-instrumentation enabled")
    except ImportError:
        logger.warning(
            "opentelemetry-instrumentation-fastapi not installed — "
            "request tracing disabled"
        )

    logger.info("DocuMind API started")
    yield

    # ── Shutdown ────────────────────────────────────────────────
    logger.info("DocuMind API shutting down")


# ── Error handlers ─────────────────────────────────────────────────


def _request_id(request: Request) -> str:
    """Extract or generate a request ID for correlation."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


# ── Factory ────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="DocuMind API",
        description="Intelligent Document Processing Pipeline",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ──────────────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": str(exc),
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(FileNotFoundError)
    async def not_found_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "error": "not_found",
                "detail": str(exc),
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred.",
                "request_id": _request_id(request),
            },
        )

    # ── Routers ─────────────────────────────────────────────────
    from documind.api.endpoints.documents import router as documents_router
    from documind.api.endpoints.health import router as health_router
    from documind.api.endpoints.search import router as search_router
    from documind.api.endpoints.events import router as events_router

    # ── Root redirect ───────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    app.include_router(health_router, tags=["health"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(search_router, prefix="/search", tags=["search"])
    app.include_router(events_router, tags=["events"])

    return app


# Module-level app instance — used by uvicorn
app = create_app()
