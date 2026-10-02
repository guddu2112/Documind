"""Offline pipeline smoke tests — no Azure credentials required.

Verifies that the ``BACKEND=local`` code path can:

* Boot the pipeline with all local services (SQLite / Chroma / Ollama).
* Ingest a small text sample end-to-end.
* Persist a record in SQLite.
* Return the doc from a semantic search in Chroma.

The tests skip automatically if Ollama isn't reachable or if the optional
``offline`` extras aren't installed.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


# Force the local backend BEFORE anything imports settings.
os.environ.setdefault("BACKEND", "local")
os.environ.setdefault("AUTH_MODE", "none")


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "samples" / "contracts" / "software-license-agreement.txt"


def _ollama_available() -> bool:
    try:
        import httpx

        from documind.core.config.settings import settings

        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
        return r.status_code < 500
    except Exception:
        return False


offline_extras = pytest.importorskip("chromadb", reason="chromadb not installed — install with pip install -e '.[offline]'")
pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


pytestmark = [
    pytest.mark.skipif(not SAMPLE.exists(), reason=f"sample file missing: {SAMPLE}"),
    pytest.mark.skipif(not _ollama_available(), reason="Ollama not reachable at OLLAMA_BASE_URL"),
]


@pytest.fixture
def offline_data_dir(tmp_path, monkeypatch):
    """Isolate every offline test to its own ./data/ directory."""
    data_dir = tmp_path / "data"
    (data_dir / "chroma").mkdir(parents=True)
    (data_dir / "blobs").mkdir(parents=True)

    monkeypatch.setenv("BACKEND", "local")
    monkeypatch.setenv("AUTH_MODE", "none")
    monkeypatch.setenv("CHROMA_PATH", str(data_dir / "chroma"))
    monkeypatch.setenv("SQLITE_PATH", str(data_dir / "documind.sqlite"))
    monkeypatch.setenv("LOCAL_BLOB_DIR", str(data_dir / "blobs"))

    # Force a fresh settings singleton
    import importlib

    import documind.core.config.settings as settings_module

    importlib.reload(settings_module)

    # Also reload the factory so it picks up the new settings
    import documind.services.factory as factory_module

    importlib.reload(factory_module)

    yield data_dir

    # Best-effort cleanup (Windows may still hold Chroma handles)
    shutil.rmtree(data_dir, ignore_errors=True)


def test_factory_returns_local_implementations(offline_data_dir):
    """The factory dispatches to local classes when BACKEND=local."""
    from documind.services import factory
    from documind.services.local.chroma_search import ChromaSearchService
    from documind.services.local.filesystem_blob import LocalBlobStorage
    from documind.services.local.local_extractor import LocalExtractor
    from documind.services.local.sqlite_store import SQLiteRecordStore

    assert isinstance(factory.get_record_store(), SQLiteRecordStore)
    assert isinstance(factory.get_blob_store(), LocalBlobStorage)
    assert isinstance(factory.get_search_service(), ChromaSearchService)
    assert isinstance(factory.get_extractor(), LocalExtractor)
    # LLM caller + embedding fn are callables
    assert callable(factory.get_llm_caller())
    assert callable(factory.get_embedding_fn())


def test_sqlite_roundtrip(offline_data_dir):
    """SQLite record store should create/get/update records."""
    from documind.core.models.base import DocumentRecord, ProcessingStatus
    from documind.services import factory

    store = factory.get_record_store()
    rec = DocumentRecord(
        document_id="test-001",
        doc_type="contract",
        source_filename="sample.txt",
        status=ProcessingStatus.PENDING,
    )
    store.create_record(rec)

    fetched = store.get_record("test-001", "contract")
    assert fetched["document_id"] == "test-001"
    assert fetched["status"] == ProcessingStatus.PENDING.value

    store.update_status("test-001", "contract", ProcessingStatus.COMPLETED)
    fetched2 = store.query_by_document_id("test-001")
    assert fetched2 is not None
    assert fetched2["status"] == ProcessingStatus.COMPLETED.value


def test_local_extractor_reads_txt(offline_data_dir):
    """LocalExtractor should read plain-text files."""
    from documind.services import factory

    extractor = factory.get_extractor()
    result = extractor.analyze_document(SAMPLE.read_bytes())
    assert result.content
    assert "license" in result.content.lower()


def test_chroma_semantic_search(offline_data_dir):
    """ChromaSearchService should return the doc as top hit."""
    from documind.services import factory

    svc = factory.get_search_service()
    text = SAMPLE.read_text(encoding="utf-8", errors="replace")

    doc = {
        "id": "smoke-doc-1",
        "document_id": "smoke-doc-1",
        "doc_type": "contract",
        "content": text,
        "summary": "Software license agreement between licensor and licensee.",
        "metadata": {"filename": "software-license-agreement.txt"},
    }
    svc.upload_document(doc)

    hits = svc.semantic_search(query="license termination clause", top=3)
    assert hits, "expected at least one search hit"
    assert hits[0]["id"] == "smoke-doc-1"


@pytest.mark.slow
def test_full_pipeline_offline(offline_data_dir):
    """End-to-end: text sample → PENDING → COMPLETED, indexed in Chroma."""
    from documind.agents.analysis.agent import AnalysisExecutor
    from documind.agents.extraction.agent import ExtractionExecutor
    from documind.agents.ingestion.agent import IngestionExecutor
    from documind.agents.orchestrator.workflow import DocumentPipeline
    from documind.agents.search.agent import SearchExecutor
    from documind.core.models.base import DocumentRecord, ProcessingStatus
    from documind.doctypes.registry import DocTypeRegistry
    from documind.services import factory
    from documind.services.prompt_loader import PromptLoader

    registry = DocTypeRegistry()
    registry.load()

    pipeline = DocumentPipeline(
        ingestion=IngestionExecutor(registry=registry, blob_service=factory.get_blob_store()),
        extraction=ExtractionExecutor(registry=registry, di_service=factory.get_extractor()),
        analysis=AnalysisExecutor(
            registry=registry,
            prompt_loader=PromptLoader(),
            llm_caller=factory.get_llm_caller(),
        ),
        search=SearchExecutor(registry=registry, search_service=factory.get_search_service()),
        cosmos=factory.get_record_store(),
    )

    store = factory.get_record_store()
    store.create_record(
        DocumentRecord(
            document_id="e2e-001",
            doc_type="contract",
            source_filename=SAMPLE.name,
            status=ProcessingStatus.PENDING,
        )
    )

    import asyncio

    asyncio.run(
        pipeline.run(
            file_bytes=SAMPLE.read_bytes(),
            filename=SAMPLE.name,
            doc_type_hint="contract",
            document_id="e2e-001",
        )
    )

    final = store.get_record("e2e-001", "contract")
    assert final["status"] == ProcessingStatus.COMPLETED.value
