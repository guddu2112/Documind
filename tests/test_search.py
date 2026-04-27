"""Tests for the Search & Retrieval Agent — tools and executor.

Validates document indexing, semantic search, faceted search, and
the full search executor flow.
"""

import pytest

from documind.agents.search.tools.tools import (
    faceted_search,
    index_document,
    semantic_search,
)
from documind.agents.search.agent import SearchExecutor, SearchOutput
from documind.agents.analysis.agent import AnalysisOutput
from documind.agents.extraction.agent import ExtractionOutput
from documind.agents.ingestion.agent import IngestionOutput
from documind.core.models.base import DocumentRecord


class TestIndexDocument:
    """Tests for the index_document tool."""

    def test_builds_search_doc_with_common_fields(
        self,
        registry,
        mock_search_service,
        sample_extraction_result,
        sample_analysis_result,
    ):
        """The search document should include id, doc_type, content,
        summary, and fields from the doc-type search_field_mappings."""
        result = index_document(
            extraction=sample_extraction_result,
            analysis=sample_analysis_result,
            registry=registry,
            search_service=mock_search_service,
        )
        assert result["succeeded"] is True

        # Verify the search service received the correct document
        call_args = mock_search_service.index_document.call_args
        search_doc = call_args[0][0]
        assert search_doc["id"] == "test-doc-001"
        assert search_doc["doc_type"] == "rfp"
        assert "content" in search_doc
        assert "summary" in search_doc

    def test_includes_risk_summary(
        self,
        registry,
        mock_search_service,
        sample_extraction_result,
        sample_analysis_result,
    ):
        """Risks should be serialised as a searchable string."""
        index_document(
            extraction=sample_extraction_result,
            analysis=sample_analysis_result,
            registry=registry,
            search_service=mock_search_service,
        )
        call_args = mock_search_service.index_document.call_args
        search_doc = call_args[0][0]
        assert "Tight timeline" in search_doc.get("risks", "")


class TestSemanticSearch:
    """Tests for the semantic_search tool."""

    def test_returns_results(self, mock_search_service):
        """Should return a list of result dicts from the search service."""
        results = semantic_search(
            query="document processing",
            search_service=mock_search_service,
        )
        assert len(results) == 1
        assert results[0]["id"] == "doc-1"
        mock_search_service.semantic_search.assert_called_once()

    def test_passes_filters(self, mock_search_service):
        """Filters should be forwarded to the search service."""
        semantic_search(
            query="RFP",
            search_service=mock_search_service,
            filters="doc_type eq 'rfp'",
        )
        call_kwargs = mock_search_service.semantic_search.call_args.kwargs
        assert call_kwargs["filters"] == "doc_type eq 'rfp'"


class TestFacetedSearch:
    """Tests for the faceted_search tool."""

    def test_returns_results_and_facets(self, mock_search_service):
        """Should return both results and facet counts."""
        result = faceted_search(
            query="contract",
            facets=["doc_type"],
            search_service=mock_search_service,
        )
        assert "results" in result
        assert "facets" in result
        assert "doc_type" in result["facets"]


class TestSearchExecutor:
    """Tests for the full Search Executor."""

    def test_full_indexing_flow(
        self,
        registry,
        mock_search_service,
        sample_extraction_result,
        sample_analysis_result,
    ):
        """The executor should index a processed document and return
        a SearchOutput with the result."""
        # Build the chain of intermediate outputs
        record = DocumentRecord(
            document_id="test-doc-001",
            doc_type="rfp",
            source_filename="test-rfp.pdf",
        )
        ingestion_out = IngestionOutput(record=record, file_bytes=b"fake")
        extraction_out = ExtractionOutput(
            extraction=sample_extraction_result,
            ingestion=ingestion_out,
        )
        analysis_out = AnalysisOutput(
            analysis=sample_analysis_result,
            extraction=extraction_out,
        )

        executor = SearchExecutor(
            registry=registry,
            search_service=mock_search_service,
        )
        output = executor.run(analysis_out)

        assert isinstance(output, SearchOutput)
        assert output.document_id == "test-doc-001"
        assert output.index_result["succeeded"] is True

    def test_search_method_delegates_to_service(
        self, registry, mock_search_service
    ):
        """The search() convenience method should call semantic_search."""
        executor = SearchExecutor(
            registry=registry,
            search_service=mock_search_service,
        )
        results = executor.search("test query")
        assert len(results) == 1
        mock_search_service.semantic_search.assert_called_once()
