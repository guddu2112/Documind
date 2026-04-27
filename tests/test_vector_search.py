"""Tests for the VectorSearchService — Cosmos DB-backed search.

Validates that:
    - Documents are indexed (upserted) into Cosmos DB.
    - Embeddings are auto-generated when content is present.
    - Vector search queries return results.
    - Faceted search returns results and facet counts.
    - The service handles errors gracefully.
"""

import pytest
from unittest.mock import MagicMock, patch, call


class TestVectorSearchServiceIndexing:
    """Tests for document indexing operations."""

    def test_index_document_upserts_to_cosmos(self, mock_vector_search_service):
        """Should call upsert_item on the Cosmos container."""
        service = mock_vector_search_service

        doc = {
            "id": "doc-001",
            "doc_type": "rfp",
            "content": "Test content",
            "embedding": [0.1] * 1536,  # pre-computed embedding
        }
        result = service.index_document(doc)

        assert result["succeeded"] is True
        assert result["key"] == "doc-001"

    def test_auto_generates_embedding_when_missing(self, mock_vector_search_service):
        """When embedding is not provided but content is, the service
        should auto-generate the embedding using the embedding function."""
        service = mock_vector_search_service

        doc = {
            "id": "doc-002",
            "doc_type": "rfp",
            "content": "Some document content",
        }
        result = service.index_document(doc)

        assert result["succeeded"] is True
        # The document should now have an embedding field
        upserted_doc = service._container.upsert_item.call_args[1]["body"]
        assert "embedding" in upserted_doc
        assert len(upserted_doc["embedding"]) == 1536

    def test_includes_summary_in_embedding_input(self, mock_vector_search_service):
        """When both content and summary are present, both should be
        used for richer embedding generation."""
        service = mock_vector_search_service
        calls = []

        def tracking_embed(text):
            calls.append(text)
            return [0.1] * 1536

        service._embedding_fn = tracking_embed

        doc = {
            "id": "doc-003",
            "doc_type": "rfp",
            "content": "Main content",
            "summary": "Brief summary",
        }
        service.index_document(doc)

        # The embedding function should receive summary + content
        assert len(calls) == 1
        assert "Brief summary" in calls[0]
        assert "Main content" in calls[0]

    def test_handles_upsert_failure(self, mock_vector_search_service):
        """If Cosmos upsert fails, the result should indicate failure."""
        service = mock_vector_search_service
        service._container.upsert_item.side_effect = Exception("Cosmos unavailable")

        doc = {
            "id": "doc-004",
            "doc_type": "rfp",
            "content": "Test",
            "embedding": [0.1] * 1536,
        }
        result = service.index_document(doc)

        assert result["succeeded"] is False
        assert "error" in result


class TestVectorSearchServiceSearch:
    """Tests for search operations."""

    def test_semantic_search_returns_results(self, mock_vector_search_service):
        """Should return results from the Cosmos vector query."""
        service = mock_vector_search_service

        results = service.semantic_search("document processing", top=5)

        assert len(results) == 1
        assert results[0]["id"] == "doc-1"
        assert "SimilarityScore" in results[0]

    def test_semantic_search_with_filters(self, mock_vector_search_service):
        """Filters should be included in the SQL WHERE clause."""
        service = mock_vector_search_service

        service.semantic_search(
            "RFP requirements",
            top=5,
            filters="c.doc_type = 'rfp'",
        )

        # Check that query_items was called
        service._container.query_items.assert_called()
        # The SQL should include the filter
        call_args = service._container.query_items.call_args
        sql = call_args[1]["query"]
        assert "c.doc_type = 'rfp'" in sql

    def test_faceted_search_returns_results_and_facets(
        self, mock_vector_search_service
    ):
        """Should return both search results and facet counts."""
        service = mock_vector_search_service

        # Mock the facet aggregation query to return results
        service._container.query_items.return_value = [
            {"value": "rfp", "count": 3},
        ]

        result = service.faceted_search("contract", facets=["doc_type"])

        assert "results" in result
        assert "facets" in result
        assert "doc_type" in result["facets"]
        assert len(result["facets"]["doc_type"]) >= 1


class TestVectorSearchServiceEmbedding:
    """Tests for the embedding function integration."""

    def test_custom_embedding_function(self):
        """A custom embedding function should be used instead of the default."""
        from documind.services.vector_search import VectorSearchService

        # Custom embedding function that returns zeros
        custom_embed = lambda text: [0.0] * 1536

        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_db = MagicMock()
        mock_client.get_database_client.return_value = mock_db
        mock_db.get_container_client.return_value = mock_container

        service = VectorSearchService(
            client=mock_client,
            database_name="test-db",
            container_name="test-container",
            embedding_fn=custom_embed,
        )

        doc = {"id": "test-1", "content": "Hello"}
        service.index_document(doc)

        # The upserted doc should have zero embeddings
        upserted = mock_container.upsert_item.call_args[1]["body"]
        assert upserted["embedding"] == [0.0] * 1536
