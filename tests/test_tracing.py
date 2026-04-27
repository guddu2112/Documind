"""Tests for OpenTelemetry tracing integration.

Validates that:
    - configure_telemetry() sets up a working tracer.
    - create_pipeline_span() creates spans with correct attributes.
    - @traced decorator wraps functions in spans.
    - Exceptions are recorded on spans.
    - Async functions are also traced correctly.
"""

import asyncio

import pytest
from unittest.mock import patch, MagicMock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from documind.core.tracing import (
    configure_telemetry,
    create_pipeline_span,
    traced,
    _TRACER_NAME,
    _get_tracer,
)
import documind.core.tracing as tracing_module


# Set up a single TracerProvider with InMemorySpanExporter for the whole module.
# OTEL only allows one set_tracer_provider call per process.
_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset the global tracer and clear exported spans before each test."""
    _exporter.clear()
    tracing_module._tracer = trace.get_tracer(_TRACER_NAME)
    yield
    tracing_module._tracer = None


class TestConfigureTelemetry:
    """Tests for the configure_telemetry() function."""

    def test_configures_without_connection_string(self):
        """Should set up a tracer when no connection string is available."""
        with patch.object(
            tracing_module.settings,
            "applicationinsights_connection_string",
            "",
        ):
            configure_telemetry()

        tracer = _get_tracer()
        assert tracer is not None

    def test_configures_with_connection_string(self):
        """Should attempt to set up Azure Monitor when connection string is provided."""
        mock_configure = MagicMock()
        mock_module = MagicMock()
        mock_module.configure_azure_monitor = mock_configure
        with patch.dict(
            "sys.modules",
            {"azure.monitor.opentelemetry": mock_module},
        ):
            configure_telemetry(connection_string="InstrumentationKey=test-key")

        mock_configure.assert_called_once()

    def test_falls_back_when_azure_monitor_not_installed(self):
        """Should fall back gracefully if azure-monitor-opentelemetry is missing."""
        mock_module = MagicMock()
        mock_module.configure_azure_monitor = MagicMock(side_effect=ImportError("No module"))
        with patch.dict(
            "sys.modules",
            {"azure.monitor.opentelemetry": mock_module},
        ):
            configure_telemetry(connection_string="InstrumentationKey=test")

        tracer = _get_tracer()
        assert tracer is not None


class TestCreatePipelineSpan:
    """Tests for the create_pipeline_span context manager."""

    def test_creates_span_with_name(self):
        """Should create a span with the given name."""
        with create_pipeline_span("document.pipeline"):
            pass

        spans = _exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "document.pipeline"

    def test_attaches_document_id(self):
        """Should attach document.id as a span attribute."""
        with create_pipeline_span("document.pipeline", document_id="doc-123"):
            pass

        spans = _exporter.get_finished_spans()
        assert spans[0].attributes["document.id"] == "doc-123"

    def test_attaches_custom_attributes(self):
        """Should attach extra keyword arguments as span attributes."""
        with create_pipeline_span(
            "document.extraction", doc_type="rfp", pages=42
        ):
            pass

        spans = _exporter.get_finished_spans()
        assert spans[0].attributes["doc_type"] == "rfp"
        assert spans[0].attributes["pages"] == 42

    def test_records_exception(self):
        """Exceptions should be recorded on the span."""
        with pytest.raises(ValueError, match="test error"):
            with create_pipeline_span("document.analysis") as span:
                raise ValueError("test error")

        spans = _exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert len(spans[0].events) >= 1

    def test_nested_spans(self):
        """Nested spans should have parent-child relationship."""
        with create_pipeline_span("document.pipeline") as parent:
            with create_pipeline_span("document.ingestion") as child:
                pass

        spans = _exporter.get_finished_spans()
        assert len(spans) == 2
        child_span = spans[0]
        assert child_span.parent is not None


class TestTracedDecorator:
    """Tests for the @traced decorator."""

    def test_sync_function_traced(self):
        """@traced should create a span for sync functions."""

        @traced("document.test.sync")
        def my_func(x, y):
            return x + y

        result = my_func(1, 2)

        assert result == 3
        spans = _exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "document.test.sync"

    def test_async_function_traced(self):
        """@traced should create a span for async functions."""

        @traced("document.test.async")
        async def my_async_func(x):
            return x * 2

        result = asyncio.new_event_loop().run_until_complete(my_async_func(5))

        assert result == 10
        spans = _exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "document.test.async"

    def test_extracts_document_id(self):
        """@traced should extract document_id from args when extractor is provided."""

        @traced(
            "document.test.extract",
            extract_doc_id=lambda doc_id, _: doc_id,
        )
        def process(doc_id, data):
            return data

        process("doc-456", {"key": "value"})

        spans = _exporter.get_finished_spans()
        assert spans[0].attributes["document.id"] == "doc-456"

    def test_exception_recorded_in_decorator(self):
        """Exceptions in traced functions should be recorded on the span."""

        @traced("document.test.error")
        def failing_func():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            failing_func()

        spans = _exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    def test_preserves_function_metadata(self):
        """@traced should preserve the original function's name and docstring."""

        @traced("test.metadata")
        def my_documented_func():
            """This is my docstring."""
            pass

        assert my_documented_func.__name__ == "my_documented_func"
        assert my_documented_func.__doc__ == "This is my docstring."
