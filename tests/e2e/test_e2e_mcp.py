"""E2E tests for MCP tools against live Azure OpenAI.

Tests each MCP tool function directly (not via transport) with real
LLM calls and real sample documents.

The MCP server module uses its own ``_get_llm_caller()`` which reads
API key from settings.  For E2E tests we patch it to use
DefaultAzureCredential (same as the pipeline).

Run:  pytest tests/e2e/test_e2e_mcp.py -v --e2e
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="module")
def rfp_text(sample_rfp_path):
    return sample_rfp_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def contract_text(sample_contract_path):
    return sample_contract_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def spec_text(sample_spec_path):
    return sample_spec_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def patched_llm(settings):
    """Patch the MCP server's _get_llm_caller to use DefaultAzureCredential."""
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=settings.azure_openai_api_version,
    )

    def _caller(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=settings.foundry_model_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
        )
        return resp.choices[0].message.content or ""

    with patch("documind.mcp.server._get_llm_caller", return_value=_caller):
        yield


class TestListDocTypes:
    def test_list_doc_types_returns_all_three(self, env_loaded):
        from documind.mcp.server import list_doc_types

        result = json.loads(list_doc_types())
        names = [d["name"] for d in result]
        assert "rfp" in names
        assert "contract" in names
        assert "spec" in names

    def test_each_type_has_analysis_tasks(self, env_loaded):
        from documind.mcp.server import list_doc_types

        result = json.loads(list_doc_types())
        for doc_type in result:
            assert len(doc_type["analysis_tasks"]) >= 1
            for task in doc_type["analysis_tasks"]:
                assert "name" in task
                assert "description" in task


class TestSummarize:
    @pytest.mark.timeout(120)
    def test_summarize_rfp(self, env_loaded, patched_llm, rfp_text):
        """Summarize a real RFP doc — should return valid JSON with key fields."""
        from documind.mcp.server import summarize

        try:
            result_str = summarize(rfp_text, doc_type="rfp")
        except Exception as exc:
            if "500" in str(exc) or "InternalServerError" in type(exc).__name__:
                pytest.skip(f"Azure OpenAI transient error: {exc}")
            raise

        result = json.loads(result_str)

        # Should not be an error
        assert "error" not in result

        # Should contain expected analysis fields
        assert isinstance(result, dict)
        # LLM output varies, but we can check it's non-trivial
        assert len(result_str) > 100


class TestExtractClauses:
    @pytest.mark.timeout(120)
    def test_extract_clauses_contract(self, env_loaded, patched_llm, contract_text):
        """Extract clauses from a real contract — should return valid JSON."""
        from documind.mcp.server import extract_clauses

        try:
            result_str = extract_clauses(contract_text, doc_type="contract")
        except Exception as exc:
            if "500" in str(exc) or "InternalServerError" in type(exc).__name__:
                pytest.skip(f"Azure OpenAI transient error: {exc}")
            raise

        result = json.loads(result_str)

        assert "error" not in result
        assert isinstance(result, dict)
        assert len(result_str) > 100


class TestCheckCompliance:
    @pytest.mark.timeout(120)
    def test_check_compliance_spec(self, env_loaded, patched_llm, spec_text):
        """Check compliance on a real spec — should return valid JSON."""
        from documind.mcp.server import check_compliance

        try:
            result_str = check_compliance(spec_text, doc_type="spec")
        except Exception as exc:
            if "500" in str(exc) or "InternalServerError" in type(exc).__name__:
                pytest.skip(f"Azure OpenAI transient error: {exc}")
            raise

        result = json.loads(result_str)

        assert "error" not in result
        assert isinstance(result, dict)
        assert len(result_str) > 100


class TestCrossTypeErrors:
    def test_summarize_unknown_type(self, env_loaded):
        """Summarize with unknown doc type should return error JSON."""
        from documind.mcp.server import summarize

        result = json.loads(summarize("some text", doc_type="invoice"))
        assert "error" in result

    def test_extract_clauses_wrong_type(self, env_loaded):
        """extract_clauses on an rfp should fail (rfp has no extract_clauses task)."""
        from documind.mcp.server import extract_clauses

        result = json.loads(extract_clauses("some text", doc_type="rfp"))
        assert "error" in result
