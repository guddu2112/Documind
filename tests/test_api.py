"""Tests for the DocuMind FastAPI API layer.

Uses httpx AsyncClient with FastAPI's TestClient pattern.
All Azure services are mocked — no cloud connectivity needed.
"""

from __future__ import annotations

import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

# Set AUTH_MODE to none before importing the app so endpoints don't
# require authentication during tests.
os.environ["AUTH_MODE"] = "none"

from documind.api.main import create_app
from documind.core.models.base import ProcessingStatus


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health Endpoints ───────────────────────────────────────────────


class TestHealthEndpoints:
    """Tests for /health and /ready."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "documind-api"

    @pytest.mark.asyncio
    async def test_readiness_all_ok(self, client):
        """When all dependency checks pass, status should be 'ready'."""
        with (
            patch("documind.api.endpoints.health._check_cosmos") as mock_cosmos,
            patch("documind.api.endpoints.health._check_blob") as mock_blob,
            patch("documind.api.endpoints.health._check_openai") as mock_openai,
        ):
            from documind.api.schemas import ReadinessCheck

            mock_cosmos.return_value = ReadinessCheck(name="cosmos_db", status="ok")
            mock_blob.return_value = ReadinessCheck(name="blob_storage", status="ok")
            mock_openai.return_value = ReadinessCheck(name="azure_openai", status="ok")

            resp = await client.get("/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ready"
            assert len(data["checks"]) == 3

    @pytest.mark.asyncio
    async def test_readiness_degraded(self, client):
        """When a dependency check fails, status should be 'degraded'."""
        with (
            patch("documind.api.endpoints.health._check_cosmos") as mock_cosmos,
            patch("documind.api.endpoints.health._check_blob") as mock_blob,
            patch("documind.api.endpoints.health._check_openai") as mock_openai,
        ):
            from documind.api.schemas import ReadinessCheck

            mock_cosmos.return_value = ReadinessCheck(
                name="cosmos_db", status="error", detail="Connection refused"
            )
            mock_blob.return_value = ReadinessCheck(name="blob_storage", status="ok")
            mock_openai.return_value = ReadinessCheck(name="azure_openai", status="ok")

            resp = await client.get("/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"


# ── Document Endpoints ─────────────────────────────────────────────


class TestDocumentEndpoints:
    """Tests for POST /documents, GET /documents/{id}, GET /documents/{id}/analysis."""

    @pytest.mark.asyncio
    async def test_upload_returns_202(self, client):
        """Upload should return 202 with a document_id."""
        resp = await client.post(
            "/documents",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"doc_type": "rfp"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "document_id" in data
        assert data["filename"] == "test.pdf"
        assert data["doc_type"] == "rfp"

    @pytest.mark.asyncio
    async def test_upload_auto_doc_type(self, client):
        """Upload with doc_type=auto should return 'pending' as type."""
        resp = await client.post(
            "/documents",
            files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
            data={"doc_type": "auto"},
        )
        assert resp.status_code == 202
        assert resp.json()["doc_type"] == "pending"

    @pytest.mark.asyncio
    async def test_upload_empty_file_rejected(self, client):
        """Empty file upload should return 422."""
        resp = await client.post(
            "/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            data={"doc_type": "rfp"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_document_status(self, client):
        """GET /documents/{id} should return status from Cosmos."""
        mock_record = {
            "document_id": "doc-123",
            "doc_type": "rfp",
            "status": "extracting",
            "source_filename": "test.pdf",
            "uploaded_at": "2024-01-01T00:00:00",
            "completed_at": None,
            "error_message": None,
            "stages_completed": ["ingestion"],
        }

        with patch("documind.services.cosmos.CosmosService") as MockCosmos:
            MockCosmos.return_value.get_record.return_value = mock_record
            resp = await client.get("/documents/doc-123?doc_type=rfp")

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == "doc-123"
        assert data["status"] == "extracting"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client):
        """GET /documents/{id} should return 404 for unknown documents."""
        with patch("documind.services.cosmos.CosmosService") as MockCosmos:
            MockCosmos.return_value.get_record.side_effect = Exception("Not found")
            resp = await client.get("/documents/nonexistent?doc_type=rfp")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_analysis_completed(self, client):
        """GET /documents/{id}/analysis should return results for completed docs."""
        mock_record = {
            "document_id": "doc-123",
            "doc_type": "rfp",
            "status": "completed",
            "extraction": {
                "document_id": "doc-123",
                "doc_type": "rfp",
                "source_filename": "test.pdf",
                "page_count": 5,
                "raw_text": "Sample text",
                "confidence_score": 0.95,
            },
            "analysis": {
                "document_id": "doc-123",
                "doc_type": "rfp",
                "summary": "This is a summary.",
            },
        }

        with patch("documind.services.cosmos.CosmosService") as MockCosmos:
            MockCosmos.return_value.get_record.return_value = mock_record
            resp = await client.get("/documents/doc-123/analysis?doc_type=rfp")

        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction"]["page_count"] == 5
        assert data["analysis"]["summary"] == "This is a summary."

    @pytest.mark.asyncio
    async def test_get_analysis_not_completed(self, client):
        """GET /documents/{id}/analysis should return 409 for in-progress docs."""
        mock_record = {
            "document_id": "doc-123",
            "doc_type": "rfp",
            "status": "extracting",
        }

        with patch("documind.services.cosmos.CosmosService") as MockCosmos:
            MockCosmos.return_value.get_record.return_value = mock_record
            resp = await client.get("/documents/doc-123/analysis?doc_type=rfp")

        assert resp.status_code == 409


# ── Search Endpoints ───────────────────────────────────────────────


class TestSearchEndpoints:
    """Tests for POST /search."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client):
        """POST /search should return formatted results."""
        mock_results = [
            {"id": "doc-1", "content": "RFP content", "score": 0.95, "doc_type": "rfp"},
            {"id": "doc-2", "content": "Contract content", "score": 0.82, "doc_type": "contract"},
        ]

        with patch("documind.services.vector_search.VectorSearchService") as MockSearch:
            MockSearch.return_value.semantic_search.return_value = mock_results
            resp = await client.post(
                "/search",
                json={"query": "submission deadline", "top": 10},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "submission deadline"
        assert data["total"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["id"] == "doc-1"

    @pytest.mark.asyncio
    async def test_search_with_doc_type_filter(self, client):
        """POST /search with doc_type should pass filter to service."""
        with patch("documind.services.vector_search.VectorSearchService") as MockSearch:
            MockSearch.return_value.semantic_search.return_value = []
            resp = await client.post(
                "/search",
                json={"query": "deadline", "doc_type": "rfp", "top": 5},
            )

        assert resp.status_code == 200
        MockSearch.return_value.semantic_search.assert_called_once_with(
            query="deadline", top=5, filters="c.doc_type = 'rfp'"
        )

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(self, client):
        """POST /search with empty query should return 422."""
        resp = await client.post(
            "/search",
            json={"query": "", "top": 10},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_service_error(self, client):
        """POST /search should return 500 if the search service fails."""
        with patch("documind.services.vector_search.VectorSearchService") as MockSearch:
            MockSearch.return_value.semantic_search.side_effect = Exception("Cosmos down")
            resp = await client.post(
                "/search",
                json={"query": "test query"},
            )

        assert resp.status_code == 500


# ── Error Handling ─────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for global exception handlers."""

    @pytest.mark.asyncio
    async def test_404_includes_request_id(self, client):
        """Not-found responses should include request_id."""
        with patch("documind.services.cosmos.CosmosService") as MockCosmos:
            MockCosmos.return_value.get_record.side_effect = Exception("nope")
            resp = await client.get(
                "/documents/missing?doc_type=rfp",
                headers={"X-Request-ID": "req-abc-123"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unknown_route_returns_404(self, client):
        """Hitting a non-existent route should return 404."""
        resp = await client.get("/nonexistent")
        assert resp.status_code == 404
