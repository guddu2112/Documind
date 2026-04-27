"""Tests for the Orchestrator — full pipeline integration.

These tests validate the sequential Ingest → Extract → Analyze → Index
pipeline using all mocked services.  They verify:
- Happy path: all stages complete successfully
- Error handling: pipeline stops at the failed stage
- Stage tracking: stages_completed list is accurate
"""

import pytest
from unittest.mock import MagicMock

from documind.agents.orchestrator.workflow import DocumentPipeline, PipelineResult
from documind.agents.ingestion.agent import IngestionExecutor
from documind.agents.extraction.agent import ExtractionExecutor
from documind.agents.analysis.agent import AnalysisExecutor
from documind.agents.search.agent import SearchExecutor
from documind.core.models.base import ProcessingStatus


@pytest.fixture
def pipeline(
    registry,
    mock_blob_service,
    mock_di_service,
    mock_search_service,
    mock_llm_caller,
    prompt_loader,
):
    """Build a full pipeline with all real executors and mocked services.

    This is as close to integration testing as we can get without
    actual Azure services.
    """
    ingestion = IngestionExecutor(
        registry=registry,
        blob_service=mock_blob_service,
    )
    extraction = ExtractionExecutor(
        registry=registry,
        di_service=mock_di_service,
    )
    analysis = AnalysisExecutor(
        registry=registry,
        prompt_loader=prompt_loader,
        llm_caller=mock_llm_caller,
    )
    search = SearchExecutor(
        registry=registry,
        search_service=mock_search_service,
    )

    return DocumentPipeline(
        ingestion=ingestion,
        extraction=extraction,
        analysis=analysis,
        search=search,
        cosmos=None,  # skip Cosmos for unit tests
    )


class TestDocumentPipeline:
    """Tests for the full document processing pipeline."""

    def test_happy_path_completes_all_stages(self, pipeline, sample_pdf_bytes):
        """A valid document should pass through all four stages and
        end with COMPLETED status."""
        result = pipeline.process(
            file_bytes=sample_pdf_bytes,
            filename="proposal.pdf",
            doc_type_hint="rfp",
        )

        assert result.status == ProcessingStatus.COMPLETED
        assert result.error is None
        assert result.stages_completed == [
            "ingestion",
            "extraction",
            "analysis",
            "search",
        ]
        # Verify all intermediate outputs are present
        assert result.record.doc_type == "rfp"
        assert result.extraction is not None
        assert result.analysis is not None
        assert result.search is not None
        assert result.document_id != ""

    def test_contract_document(self, pipeline):
        """Pipeline should work for contract doc type too."""
        result = pipeline.process(
            file_bytes=b"fake contract pdf",
            filename="agreement.pdf",
            doc_type_hint="contract",
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert result.record.doc_type == "contract"
        assert len(result.stages_completed) == 4

    def test_spec_document(self, pipeline):
        """Pipeline should work for spec doc type too."""
        result = pipeline.process(
            file_bytes=b"fake spec content",
            filename="requirements.xlsx",
            doc_type_hint="spec",
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert result.record.doc_type == "spec"

    def test_ingestion_failure_stops_pipeline(
        self, registry, mock_blob_service, mock_di_service, mock_search_service,
        mock_llm_caller, prompt_loader,
    ):
        """If ingestion fails, the pipeline should stop and record the error."""
        # Make blob upload fail
        mock_blob_service.upload_document.side_effect = Exception("Storage unavailable")

        ingestion = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )
        extraction = ExtractionExecutor(registry=registry, di_service=mock_di_service)
        analysis = AnalysisExecutor(
            registry=registry, prompt_loader=prompt_loader, llm_caller=mock_llm_caller,
        )
        search = SearchExecutor(registry=registry, search_service=mock_search_service)

        pipeline = DocumentPipeline(
            ingestion=ingestion,
            extraction=extraction,
            analysis=analysis,
            search=search,
        )
        result = pipeline.process(b"fake", "test.pdf", doc_type_hint="rfp")

        assert result.status == ProcessingStatus.FAILED
        assert "ingestion" in result.error
        assert result.stages_completed == []  # nothing completed

    def test_extraction_failure_preserves_ingestion(
        self, registry, mock_blob_service, mock_di_service, mock_search_service,
        mock_llm_caller, prompt_loader,
    ):
        """If extraction fails, ingestion results should be preserved."""
        # Make DI fail
        mock_di_service.analyze_document.side_effect = Exception("DI unavailable")

        ingestion = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )
        extraction = ExtractionExecutor(registry=registry, di_service=mock_di_service)
        analysis = AnalysisExecutor(
            registry=registry, prompt_loader=prompt_loader, llm_caller=mock_llm_caller,
        )
        search = SearchExecutor(registry=registry, search_service=mock_search_service)

        pipeline = DocumentPipeline(
            ingestion=ingestion,
            extraction=extraction,
            analysis=analysis,
            search=search,
        )
        result = pipeline.process(b"fake", "test.pdf", doc_type_hint="rfp")

        assert result.status == ProcessingStatus.FAILED
        assert "extraction" in result.error
        assert result.stages_completed == ["ingestion"]
        assert result.record.blob_url != ""  # ingestion succeeded

    def test_analysis_failure_preserves_extraction(
        self, registry, mock_blob_service, mock_di_service, mock_search_service,
        prompt_loader,
    ):
        """If analysis fails, extraction results should be preserved."""
        # Make LLM fail
        def failing_llm(prompt):
            raise Exception("GPT-4o unavailable")

        ingestion = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )
        extraction = ExtractionExecutor(registry=registry, di_service=mock_di_service)
        analysis = AnalysisExecutor(
            registry=registry, prompt_loader=prompt_loader, llm_caller=failing_llm,
        )
        search = SearchExecutor(registry=registry, search_service=mock_search_service)

        pipeline = DocumentPipeline(
            ingestion=ingestion,
            extraction=extraction,
            analysis=analysis,
            search=search,
        )
        result = pipeline.process(b"fake", "test.pdf", doc_type_hint="rfp")

        assert result.status == ProcessingStatus.FAILED
        assert "analysis" in result.error
        assert result.stages_completed == ["ingestion", "extraction"]
        assert result.extraction is not None

    def test_search_failure_preserves_analysis(
        self, registry, mock_blob_service, mock_di_service, mock_search_service,
        mock_llm_caller, prompt_loader,
    ):
        """If search indexing fails, analysis results should be preserved."""
        # Make search fail
        mock_search_service.index_document.side_effect = Exception("Search unavailable")

        ingestion = IngestionExecutor(
            registry=registry,
            blob_service=mock_blob_service,
        )
        extraction = ExtractionExecutor(registry=registry, di_service=mock_di_service)
        analysis = AnalysisExecutor(
            registry=registry, prompt_loader=prompt_loader, llm_caller=mock_llm_caller,
        )
        search = SearchExecutor(registry=registry, search_service=mock_search_service)

        pipeline = DocumentPipeline(
            ingestion=ingestion,
            extraction=extraction,
            analysis=analysis,
            search=search,
        )
        result = pipeline.process(b"fake", "test.pdf", doc_type_hint="rfp")

        assert result.status == ProcessingStatus.FAILED
        assert "search" in result.error
        assert result.stages_completed == ["ingestion", "extraction", "analysis"]
        assert result.analysis is not None
