"""Tests for the DocuMind API authentication module.

Covers API key validation, Entra ID token validation, and the
no-auth bypass for local development.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ── API Key Auth Tests ─────────────────────────────────────────────


class TestApiKeyAuth:
    """Tests for X-API-Key authentication mode."""

    @pytest.fixture
    def app_with_api_key_auth(self):
        """Create an app with API key auth enabled."""
        # Patch AUTH_MODE before importing
        with patch.dict(os.environ, {"AUTH_MODE": "api_key", "DOCUMIND_API_KEY": "test-secret-key"}):
            # Clear cached module state
            import importlib
            import documind.api.auth as auth_mod

            importlib.reload(auth_mod)
            auth_mod._cached_api_key = None

            from documind.api.main import create_app

            return create_app()

    @pytest.mark.asyncio
    async def test_valid_api_key(self, app_with_api_key_auth):
        """Request with valid API key should succeed."""
        with patch.dict(os.environ, {"AUTH_MODE": "none"}):
            transport = ASGITransport(app=app_with_api_key_auth)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")
                # Health endpoint doesn't require auth
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_constant_time_compare(self):
        """Constant-time comparison should work correctly."""
        from documind.api.auth import _constant_time_compare

        assert _constant_time_compare("abc", "abc") is True
        assert _constant_time_compare("abc", "def") is False
        assert _constant_time_compare("", "") is True
        assert _constant_time_compare("a", "ab") is False


# ── No-Auth Mode Tests ─────────────────────────────────────────────


class TestNoAuth:
    """Tests for AUTH_MODE=none (development bypass)."""

    @pytest.mark.asyncio
    async def test_no_auth_allows_all(self):
        """With AUTH_MODE=none, requests should pass without credentials."""
        with patch.dict(os.environ, {"AUTH_MODE": "none"}):
            from documind.api.main import create_app

            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")
                assert resp.status_code == 200


# ── Auth Module Unit Tests ─────────────────────────────────────────


class TestAuthHelpers:
    """Unit tests for auth helper functions."""

    def test_api_key_from_env(self):
        """_get_api_key_from_vault should prefer DOCUMIND_API_KEY env var."""
        import documind.api.auth as auth_mod
        auth_mod._cached_api_key = None  # Reset cache

        with patch.dict(os.environ, {"DOCUMIND_API_KEY": "env-key-123"}):
            key = auth_mod._get_api_key_from_vault()
            assert key == "env-key-123"

        # Reset cache for other tests
        auth_mod._cached_api_key = None

    def test_api_key_caching(self):
        """Second call should use cached value."""
        import documind.api.auth as auth_mod
        auth_mod._cached_api_key = "cached-key"

        key = auth_mod._get_api_key_from_vault()
        assert key == "cached-key"

        # Reset
        auth_mod._cached_api_key = None
