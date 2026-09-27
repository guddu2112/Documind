"""Shared fixtures for end-to-end tests.

These tests hit REAL Azure services — Cosmos DB, Blob Storage,
Document Intelligence, Azure OpenAI, etc.

Requirements:
  1. A populated .env file with valid Azure credentials.
  2. Azure resources provisioned (via ``azd up`` or ``make infra-apply``).
  3. Run with:  pytest tests/e2e/ -v --tb=short

The ``e2e`` marker is applied automatically to every test in this
directory via the ``pytest_collection_modifyitems`` hook below.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

# ── Marker: skip E2E tests unless --e2e flag is passed ─────────────

E2E_REASON = "E2E tests require --e2e flag and Azure credentials"


def pytest_addoption(parser):
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests against live Azure services.",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test in tests/e2e/ and skip unless --e2e."""
    if config.getoption("--e2e"):
        return  # user opted in — run everything
    skip_e2e = pytest.mark.skip(reason=E2E_REASON)
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(skip_e2e)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def env_loaded():
    """Load .env and verify required variables are set."""
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        pytest.skip(f".env file not found at {env_path}")

    load_dotenv(env_path, override=False)

    required = [
        "AZURE_COSMOS_ENDPOINT",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_DOC_INTELLIGENCE_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)}")

    return True


@pytest.fixture(scope="session")
def settings(env_loaded):
    """Return fresh Settings loaded from .env."""
    from documind.core.config.settings import Settings

    return Settings()


@pytest.fixture(scope="session")
def blob_service(settings):
    """Real BlobStorageService."""
    from documind.services.blob_storage import BlobStorageService

    return BlobStorageService()


@pytest.fixture(scope="session")
def cosmos_service(settings):
    """Real CosmosService."""
    from documind.services.cosmos import CosmosService

    return CosmosService()


@pytest.fixture(scope="session")
def di_service(settings):
    """Real DocumentIntelligenceService."""
    from documind.services.document_intelligence import DocumentIntelligenceService

    return DocumentIntelligenceService()


@pytest.fixture(scope="session")
def registry():
    """Real DocTypeRegistry loaded from YAML files."""
    from documind.doctypes.registry import DocTypeRegistry

    r = DocTypeRegistry()
    r.load()
    return r


@pytest.fixture(scope="session")
def prompt_loader():
    """Real PromptLoader."""
    from documind.services.prompt_loader import PromptLoader

    return PromptLoader()


@pytest.fixture(scope="session")
def llm_caller(settings):
    """Real LLM caller using Azure OpenAI."""
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

    def _call(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=settings.foundry_model_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
        )
        return resp.choices[0].message.content or ""

    return _call


@pytest.fixture(scope="session")
def sample_rfp_path():
    """Path to the sample RFP text file."""
    p = Path(__file__).resolve().parent.parent.parent / "samples" / "rfps" / "cloud-migration-rfp.txt"
    if not p.exists():
        pytest.skip(f"Sample file not found: {p}")
    return p


@pytest.fixture(scope="session")
def sample_contract_path():
    """Path to the sample contract text file."""
    p = Path(__file__).resolve().parent.parent.parent / "samples" / "contracts" / "professional-services-agreement.txt"
    if not p.exists():
        pytest.skip(f"Sample file not found: {p}")
    return p


@pytest.fixture(scope="session")
def sample_spec_path():
    """Path to the sample spec text file."""
    p = Path(__file__).resolve().parent.parent.parent / "samples" / "specs" / "payment-gateway-spec.txt"
    if not p.exists():
        pytest.skip(f"Sample file not found: {p}")
    return p
