"""Shared test fixtures for DocuMind test suite.

All Azure SDK clients are mocked here so tests run without any cloud
connectivity.  Each fixture is documented to explain what it provides.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the src directory is on the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documind.core.models.base import (
    AnalysisResult,
    DocumentRecord,
    ExtractionResult,
    ExtractedTable,
    KeyValuePair,
    ProcessingStatus,
    RiskItem,
    RiskSeverity,
)
from documind.doctypes.registry import DocTypeRegistry


# ── Doc-Type Registry ──────────────────────────────────────────────


@pytest.fixture
def registry() -> DocTypeRegistry:
    """Load the real doc-type YAML configs from the types/ directory.

    This validates that our YAML files parse correctly and the registry
    discovers them.
    """
    r = DocTypeRegistry()
    r.load()
    return r


# ── Sample Data ────────────────────────────────────────────────────


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Fake PDF content for testing.

    Real PDFs are binary, but for unit tests we just need non-empty bytes.
    The actual PDF parsing is done by Azure Document Intelligence which
    we mock.
    """
    return b"%PDF-1.4 fake pdf content for testing"


@pytest.fixture
def sample_filename() -> str:
    return "sample-rfp-2024.pdf"


# ── Mock Blob Storage Service ──────────────────────────────────────


@pytest.fixture
def mock_blob_service() -> MagicMock:
    """Mock BlobStorageService that records uploads without touching Azure.

    The upload_document method returns a fake blob URL so downstream
    code can verify the URL was set on the record.
    """
    service = MagicMock()
    service.upload_document.return_value = (
        "https://fakestorage.blob.core.windows.net/raw-documents/test-id/sample.pdf"
    )
    return service


# ── Mock Document Intelligence Service ─────────────────────────────


@pytest.fixture
def mock_di_result():
    """Fake Document Intelligence analysis result.

    Mimics the structure returned by the Azure SDK so our extraction
    tools can parse it without hitting the real API.
    """
    # Build a minimal mock that has the attributes our service reads
    result = MagicMock()
    result.content = "This is a sample RFP document for testing purposes."

    # Pages
    page = MagicMock()
    page.page_number = 1
    result.pages = [page]

    # Key-value pairs
    kv = MagicMock()
    kv.key.content = "Submission Deadline"
    kv.value.content = "2024-12-31"
    kv.confidence = 0.95
    result.key_value_pairs = [kv]

    # Tables — a 2x2 table
    cell_00 = MagicMock(row_index=0, column_index=0, content="Criterion")
    cell_01 = MagicMock(row_index=0, column_index=1, content="Weight")
    cell_10 = MagicMock(row_index=1, column_index=0, content="Experience")
    cell_11 = MagicMock(row_index=1, column_index=1, content="40%")
    table = MagicMock()
    table.row_count = 2
    table.column_count = 2
    table.cells = [cell_00, cell_01, cell_10, cell_11]
    table.bounding_regions = None
    result.tables = [table]

    return result


@pytest.fixture
def mock_di_service(mock_di_result) -> MagicMock:
    """Mock DocumentIntelligenceService pre-loaded with a fake result."""
    from documind.services.document_intelligence import DocumentIntelligenceService

    service = MagicMock(spec=DocumentIntelligenceService)
    service.analyze_document.return_value = mock_di_result

    # Wire up the real parsing methods on top of the mock
    # so we test our actual parsing logic against the mock data
    real_service = DocumentIntelligenceService.__new__(DocumentIntelligenceService)
    service.extract_text.side_effect = lambda r: real_service.extract_text(r)
    service.extract_key_value_pairs.side_effect = lambda r: real_service.extract_key_value_pairs(r)
    service.extract_tables.side_effect = lambda r: real_service.extract_tables(r)
    service.get_page_count.side_effect = lambda r: real_service.get_page_count(r)

    return service


# ── Mock Search Service ────────────────────────────────────────────


@pytest.fixture
def mock_search_service() -> MagicMock:
    """Mock SearchService that records indexing calls."""
    service = MagicMock()
    service.index_document.return_value = {"succeeded": True, "key": "test-id"}
    service.semantic_search.return_value = [
        {"id": "doc-1", "content": "Sample RFP content", "score": 0.95}
    ]
    service.faceted_search.return_value = {
        "results": [{"id": "doc-1"}],
        "facets": {"doc_type": [{"value": "rfp", "count": 3}]},
    }
    return service


# ── Mock LLM Caller ───────────────────────────────────────────────


@pytest.fixture
def mock_llm_caller():
    """Mock LLM that returns a valid JSON response.

    Returns structured JSON matching the expected output format of our
    analysis prompt templates, so the analysis tools can parse it.
    """
    import json

    response = json.dumps(
        {
            "executive_summary": "This RFP seeks a vendor for document processing.",
            "mandatory_requirements": ["Cloud-based solution", "24/7 support"],
            "optional_requirements": ["Mobile app"],
            "evaluation_criteria": [
                {"criterion": "Experience", "weight": "40%", "description": "Years of experience"}
            ],
            "key_dates": [{"event": "Submission deadline", "date": "2024-12-31"}],
            "budget_range": "$500K - $1M",
            "risks": [
                {
                    "title": "Tight timeline",
                    "description": "Only 30 days to submit",
                    "severity": "high",
                    "recommendation": "Start immediately",
                }
            ],
        }
    )

    def caller(prompt: str) -> str:
        return response

    return caller


# ── Prompt Loader ──────────────────────────────────────────────────


@pytest.fixture
def prompt_loader():
    """Real PromptLoader pointing at the actual prompts directory."""
    from documind.services.prompt_loader import PromptLoader

    return PromptLoader()


# ── Pre-built Intermediate Results ─────────────────────────────────


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """A pre-built ExtractionResult for testing downstream agents."""
    return ExtractionResult(
        document_id="test-doc-001",
        doc_type="rfp",
        source_filename="test-rfp.pdf",
        page_count=5,
        raw_text="This is a sample RFP document text for testing.",
        key_value_pairs=[
            KeyValuePair(key="Deadline", value="2024-12-31", confidence=0.9)
        ],
        tables=[
            ExtractedTable(
                table_id=0,
                headers=["Criterion", "Weight"],
                rows=[["Experience", "40%"]],
            )
        ],
        confidence_score=0.9,
    )


@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    """A pre-built AnalysisResult for testing search indexing."""
    return AnalysisResult(
        document_id="test-doc-001",
        doc_type="rfp",
        summary="This RFP seeks a vendor for document processing.",
        risks=[
            RiskItem(
                title="Tight timeline",
                description="Only 30 days to submit",
                severity=RiskSeverity.HIGH,
                recommendation="Start immediately",
            )
        ],
    )


# ── Mock Vector Search Service ─────────────────────────────────────


@pytest.fixture
def mock_vector_search_service() -> MagicMock:
    """Mock VectorSearchService with a mock Cosmos container.

    Provides a fully-wired mock that:
    - Tracks upsert_item calls for indexing.
    - Returns canned results for semantic_search and faceted_search.
    - Uses a simple embedding function (all 0.1 values).
    """
    from documind.services.vector_search import VectorSearchService

    mock_container = MagicMock()
    mock_container.upsert_item.return_value = None
    mock_container.query_items.return_value = [
        {"id": "doc-1", "content": "Sample RFP content", "SimilarityScore": 0.95}
    ]

    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.get_database_client.return_value = mock_db
    mock_db.get_container_client.return_value = mock_container

    # Simple embedding function for tests
    def test_embedding_fn(text: str) -> list[float]:
        return [0.1] * 1536

    service = VectorSearchService(
        client=mock_client,
        database_name="test-db",
        container_name="test-container",
        embedding_fn=test_embedding_fn,
    )

    return service
