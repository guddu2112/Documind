"""Tests for the Settings module.

Validates that Pydantic Settings loads defaults correctly and can
be overridden via environment variables.
"""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Verify that Settings reads env vars and provides sensible defaults."""

    def test_defaults_are_empty_strings(self):
        """Settings should have empty defaults so the app starts without
        any env vars — actual values come from deployment config."""
        from documind.core.config.settings import Settings

        # Create a fresh instance with no env vars
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)  # skip .env file
        assert s.foundry_project_endpoint == ""
        assert s.azure_doc_intelligence_endpoint == ""
        assert s.azure_search_index_name == "documind-index"

    def test_env_var_override(self):
        """Environment variables should override defaults."""
        from documind.core.config.settings import Settings

        env = {"FOUNDRY_PROJECT_ENDPOINT": "https://my-foundry.openai.azure.com"}
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)
        assert s.foundry_project_endpoint == "https://my-foundry.openai.azure.com"

    def test_model_deployment_default(self):
        """GPT-4o should be the default model deployment name."""
        from documind.core.config.settings import Settings

        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
        assert s.foundry_model_deployment == "gpt-4o"
