"""OpenTelemetry tracing for the DocuMind pipeline.

Instruments all pipeline stages with OTEL spans so you can see:
    - End-to-end latency per document.
    - Per-stage breakdown (ingestion, extraction, analysis, search).
    - Error correlation (which stage failed and why).
    - Custom attributes (doc_type, document_id, page_count).

All spans are exported to Azure App Insights via the
``azure-monitor-opentelemetry`` SDK, which is configured in
``configure_telemetry()``.

Architecture::

    document.pipeline (root span)
    ├── document.ingestion
    ├── document.extraction
    ├── document.analysis
    │   ├── document.analysis.summarize
    │   ├── document.analysis.extract_clauses
    │   └── document.analysis.identify_risks
    ├── document.search
    └── document.chunking (if document was chunked)

Usage::

    from documind.core.tracing import configure_telemetry, create_pipeline_span

    configure_telemetry()  # call once at startup

    with create_pipeline_span("pipeline", document_id="doc-123") as span:
        span.set_attribute("doc_type", "rfp")
        # ... run pipeline stages ...

Decorators::

    from documind.core.tracing import traced

    @traced("document.ingestion")
    def ingest(file_bytes, filename):
        ...

The ``traced`` decorator creates a child span automatically and records
exceptions if the function raises.
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Generator

from opentelemetry import trace
from opentelemetry.trace import Span, StatusCode, Tracer

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)

# DocuMind's tracer instance — all spans are created from this
_TRACER_NAME = "documind"

# Lazy-initialised tracer (set up in configure_telemetry)
_tracer: Tracer | None = None


def _get_tracer() -> Tracer:
    """Get or create the DocuMind tracer.

    If ``configure_telemetry()`` hasn't been called, returns a no-op
    tracer so code still works without tracing configured.
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(_TRACER_NAME)
    return _tracer


# ── Configuration ──────────────────────────────────────────────────


def configure_telemetry(
    connection_string: str | None = None,
    service_name: str = "documind",
) -> None:
    """Set up OpenTelemetry with Azure Monitor (App Insights) export.

    Call this once at application startup (e.g. in main.py or app factory).
    After this call, all spans created via ``create_pipeline_span`` or
    ``@traced`` will be exported to App Insights.

    Args:
        connection_string: App Insights connection string.  If None,
                           reads from settings / environment.
        service_name:      Service name that appears in App Insights.
    """
    global _tracer

    conn_str = connection_string or settings.applicationinsights_connection_string

    if not conn_str:
        logger.warning(
            "No App Insights connection string configured — "
            "tracing will use in-memory exporter only"
        )
        # Set up a basic tracer without export for local development
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(_TRACER_NAME)
        logger.info("Telemetry configured with no-op exporter")
        return

    # Configure azure-monitor-opentelemetry for full App Insights integration
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=conn_str,
            service_name=service_name,
            # Export INFO+ logs to App Insights (default is WARNING)
            logger_name="documind",
            enable_live_metrics=True,
        )
        _tracer = trace.get_tracer(_TRACER_NAME)
        logger.info(
            "Telemetry configured with App Insights export (service=%s)",
            service_name,
        )
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry not installed — tracing disabled"
        )
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(_TRACER_NAME)


# ── Span creation ──────────────────────────────────────────────────


@contextmanager
def create_pipeline_span(
    name: str,
    document_id: str = "",
    **attributes: Any,
) -> Generator[Span, None, None]:
    """Create a span for a pipeline operation.

    Use as a context manager — the span is automatically ended and any
    exceptions are recorded on it.

    Args:
        name:         Span name (e.g. "document.pipeline", "document.ingestion").
        document_id:  Document ID to attach as an attribute for correlation.
        **attributes: Additional span attributes (e.g. doc_type, page_count).

    Yields:
        The active Span object.  You can set additional attributes on it
        within the ``with`` block.

    Example::

        with create_pipeline_span("document.extraction", document_id="abc") as span:
            span.set_attribute("pages", 42)
            result = run_extraction(...)
    """
    tracer = _get_tracer()

    with tracer.start_as_current_span(name) as span:
        # Attach standard attributes
        if document_id:
            span.set_attribute("document.id", document_id)
        for key, value in attributes.items():
            span.set_attribute(key, value)

        try:
            yield span
        except Exception as exc:
            # Record the exception on the span for App Insights
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


# ── Decorator ──────────────────────────────────────────────────────


def traced(
    span_name: str,
    extract_doc_id: Callable[..., str] | None = None,
) -> Callable:
    """Decorator that wraps a function in an OTEL span.

    The span automatically:
        - Records the function's execution time.
        - Records any exception that propagates out.
        - Attaches the document_id if ``extract_doc_id`` is provided.

    Args:
        span_name:      Name for the span (e.g. "document.analysis.summarize").
        extract_doc_id: Optional callable that extracts a document_id from
                        the function's arguments.

    Example::

        @traced("document.ingestion")
        def ingest(file_bytes, filename):
            ...

        @traced("document.analysis", extract_doc_id=lambda inp: inp.document_id)
        def analyze(extraction_output):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            doc_id = ""
            if extract_doc_id:
                try:
                    doc_id = extract_doc_id(*args, **kwargs)
                except Exception:
                    pass  # best-effort extraction

            with create_pipeline_span(span_name, document_id=doc_id):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            doc_id = ""
            if extract_doc_id:
                try:
                    doc_id = extract_doc_id(*args, **kwargs)
                except Exception:
                    pass

            with create_pipeline_span(span_name, document_id=doc_id):
                return await func(*args, **kwargs)

        # Return the appropriate wrapper based on whether the function
        # is async or sync
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
