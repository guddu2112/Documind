"""E2E tests for the FastAPI endpoints against live Azure services.

These tests start the real FastAPI app (with AUTH_MODE=none) and hit
every endpoint using httpx, exercising the full stack from HTTP to
Azure SDK calls.

Run:  pytest tests/e2e/test_e2e_api.py -v --e2e
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Disable auth for E2E tests
os.environ.setdefault("AUTH_MODE", "none")


@pytest.fixture
def app(env_loaded):
    """Create a fresh FastAPI app."""
    from documind.api.main import create_app

    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health ─────────────────────────────────────────────────────────


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """GET /health should return 200 with status=healthy."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready_endpoint(self, client):
        """GET /ready should return 200 when Azure services are reachable."""
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        # Should report checks for at least Cosmos and Blob
        assert "checks" in data


# ── Document Upload & Processing ───────────────────────────────────


class TestDocumentUpload:
    @pytest.mark.asyncio
    async def test_upload_rfp_sample(self, client, sample_rfp_path: Path):
        """Upload a sample RFP and verify 202 response with document_id."""
        with open(sample_rfp_path, "rb") as f:
            resp = await client.post(
                "/documents",
                files={"file": (sample_rfp_path.name, f, "text/plain")},
                data={"doc_type": "rfp"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "document_id" in data
        assert data["filename"] == sample_rfp_path.name
        assert data["doc_type"] == "rfp"

    @pytest.mark.asyncio
    async def test_upload_contract_sample(self, client, sample_contract_path: Path):
        """Upload a sample contract."""
        with open(sample_contract_path, "rb") as f:
            resp = await client.post(
                "/documents",
                files={"file": (sample_contract_path.name, f, "text/plain")},
                data={"doc_type": "contract"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "document_id" in data
        assert data["doc_type"] == "contract"

    @pytest.mark.asyncio
    async def test_upload_spec_sample(self, client, sample_spec_path: Path):
        """Upload a sample spec."""
        with open(sample_spec_path, "rb") as f:
            resp = await client.post(
                "/documents",
                files={"file": (sample_spec_path.name, f, "text/plain")},
                data={"doc_type": "spec"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "document_id" in data
        assert data["doc_type"] == "spec"

    @pytest.mark.asyncio
    async def test_upload_rejects_empty_file(self, client):
        """Uploading an empty file should return 422."""
        resp = await client.post(
            "/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            data={"doc_type": "rfp"},
        )
        assert resp.status_code == 422


# ── Search ─────────────────────────────────────────────────────────


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results_or_empty(self, client):
        """POST /search should return 200 (may be empty if nothing indexed yet)."""
        resp = await client.post(
            "/search",
            json={"query": "cloud migration", "doc_type": "rfp"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
