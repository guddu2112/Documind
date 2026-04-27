"""Tests for the Extraction Agent — tools and executor.

Validates that Document Intelligence results are correctly parsed
into our domain models (ExtractionResult, KeyValuePair, ExtractedTable).
"""

import pytest

from documind.agents.extraction.tools.tools import (
    build_extraction_result,
    extract_key_value_pairs,
    extract_layout,
    extract_tables,
)
from documind.agents.extraction.agent import ExtractionExecutor, ExtractionOutput
from documind.agents.ingestion.agent import IngestionOutput
from documind.core.models.base import (
    DocumentRecord,
    ExtractionResult,
    ProcessingStatus,
)


class TestExtractLayout:
    """Tests for the extract_layout tool."""

    def test_calls_di_service_with_correct_model(self, mock_di_service):
        """The tool should pass the model_id to the DI service."""
        result = extract_layout(
            file_bytes=b"fake pdf",
            model_id="prebuilt-layout",
            di_service=mock_di_service,
        )
        mock_di_service.analyze_document.assert_called_once_with(
            file_bytes=b"fake pdf", model_id="prebuilt-layout"
        )
        assert result is not None


class TestExtractKeyValuePairs:
    """Tests for the extract_key_value_pairs tool."""

    def test_extracts_kv_pairs_from_result(self, mock_di_service, mock_di_result):
        """Should parse the mock DI result into KeyValuePair objects."""
        pairs = extract_key_value_pairs(mock_di_result, mock_di_service)
        assert len(pairs) == 1
        assert pairs[0].key == "Submission Deadline"
        assert pairs[0].value == "2024-12-31"
        assert pairs[0].confidence == 0.95


class TestExtractTables:
    """Tests for the extract_tables tool."""

    def test_extracts_tables_from_result(self, mock_di_service, mock_di_result):
        """Should parse the mock DI result into ExtractedTable objects."""
        tables = extract_tables(mock_di_result, mock_di_service)
        assert len(tables) == 1
        assert tables[0].headers == ["Criterion", "Weight"]
        assert tables[0].rows == [["Experience", "40%"]]


class TestBuildExtractionResult:
    """Tests for the build_extraction_result helper."""

    def test_assembles_complete_result(self, mock_di_service, mock_di_result):
        """Should combine text, KV pairs, tables, and page count into
        a single ExtractionResult."""
        result = build_extraction_result(
            document_id="test-123",
            doc_type="rfp",
            source_filename="test.pdf",
            analysis_result=mock_di_result,
            di_service=mock_di_service,
        )
        assert isinstance(result, ExtractionResult)
        assert result.document_id == "test-123"
        assert result.doc_type == "rfp"
        assert result.page_count == 1
        assert "sample RFP document" in result.raw_text
        assert len(result.key_value_pairs) == 1
        assert len(result.tables) == 1
        assert result.confidence_score == 0.95  # single KV pair with 0.95


class TestExtractionExecutor:
    """Tests for the full Extraction Executor."""

    def test_full_extraction_flow(
        self, registry, mock_di_service, sample_pdf_bytes
    ):
        """The executor should take an IngestionOutput, run DI, and
        return an ExtractionOutput with parsed results."""
        # Build a fake ingestion output
        record = DocumentRecord(
            document_id="test-456",
            doc_type="rfp",
            source_filename="rfp.pdf",
            status=ProcessingStatus.PENDING,
            blob_url="https://fake.blob.core.windows.net/raw/rfp.pdf",
        )
        ingestion_out = IngestionOutput(record=record, file_bytes=sample_pdf_bytes)

        executor = ExtractionExecutor(
            registry=registry,
            di_service=mock_di_service,
        )
        output = executor.run(ingestion_out)

        assert isinstance(output, ExtractionOutput)
        assert output.extraction.document_id == "test-456"
        assert output.extraction.doc_type == "rfp"
        assert output.extraction.page_count == 1
        assert len(output.extraction.key_value_pairs) == 1
        # Verify the DI service was called with the correct model
        mock_di_service.analyze_document.assert_called_once_with(
            file_bytes=sample_pdf_bytes,
            model_id="prebuilt-layout",  # RFP uses prebuilt-layout
        )

    def test_contract_uses_prebuilt_contract_model(
        self, registry, mock_di_service
    ):
        """Contracts should use the prebuilt-contract model from the
        doc-type YAML config."""
        record = DocumentRecord(
            document_id="contract-789",
            doc_type="contract",
            source_filename="agreement.pdf",
        )
        ingestion_out = IngestionOutput(record=record, file_bytes=b"fake")

        executor = ExtractionExecutor(
            registry=registry,
            di_service=mock_di_service,
        )
        executor.run(ingestion_out)

        # The contract.yaml specifies "prebuilt-contract" as the model
        mock_di_service.analyze_document.assert_called_once_with(
            file_bytes=b"fake",
            model_id="prebuilt-contract",
        )
