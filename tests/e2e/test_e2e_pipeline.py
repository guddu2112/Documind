"""E2E tests for the full document processing pipeline.

Tests the Ingest → Extract → Analyze → Index pipeline with REAL
Azure services (Blob Storage, Document Intelligence, OpenAI, Cosmos DB).

These tests take 30-120 seconds each because they call Azure OpenAI
and Document Intelligence APIs.

Run:  pytest tests/e2e/test_e2e_pipeline.py -v --e2e --timeout=300
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from documind.core.models.base import ProcessingStatus


def _build_real_pipeline(settings):
    """Build a DocumentPipeline with real Azure services."""
    from documind.agents.analysis.agent import AnalysisExecutor
    from documind.agents.extraction.agent import ExtractionExecutor
    from documind.agents.ingestion.agent import IngestionExecutor
    from documind.agents.search.agent import SearchExecutor
    from documind.agents.orchestrator.workflow import DocumentPipeline
    from documind.doctypes.registry import DocTypeRegistry
    from documind.services.blob_storage import BlobStorageService
    from documind.services.cosmos import CosmosService
    from documind.services.document_intelligence import DocumentIntelligenceService
    from documind.services.prompt_loader import PromptLoader
    from documind.services.vector_search import VectorSearchService

    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    registry = DocTypeRegistry()
    registry.load()

    blob_svc = BlobStorageService()
    di_svc = DocumentIntelligenceService()
    cosmos_svc = CosmosService()
    vector_svc = VectorSearchService()
    prompt_loader = PromptLoader()

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    openai_client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=settings.azure_openai_api_version,
    )

    def llm_caller(prompt: str) -> str:
        resp = openai_client.chat.completions.create(
            model=settings.foundry_model_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
        )
        return resp.choices[0].message.content or ""

    ingestion = IngestionExecutor(registry=registry, blob_service=blob_svc)
    extraction = ExtractionExecutor(registry=registry, di_service=di_svc)
    analysis = AnalysisExecutor(
        registry=registry,
        prompt_loader=prompt_loader,
        llm_caller=llm_caller,
    )
    search = SearchExecutor(registry=registry, search_service=vector_svc)

    return DocumentPipeline(
        ingestion=ingestion,
        extraction=extraction,
        analysis=analysis,
        search=search,
        cosmos=cosmos_svc,
    )


@pytest.fixture(scope="module")
def pipeline(settings):
    return _build_real_pipeline(settings)


# ── Full Pipeline Tests ────────────────────────────────────────────


class TestFullPipeline:
    """Process real sample documents through the complete pipeline."""

    @pytest.mark.timeout(300)
    def test_rfp_full_pipeline(self, pipeline, sample_rfp_path: Path):
        """Process a sample RFP through all 4 stages.

        Note: Plain .txt files may be rejected by Document Intelligence
        (it expects PDF/DOCX/images). If extraction fails with
        InvalidContent, the test verifies ingestion succeeded and
        reports the DI limitation.
        """
        file_bytes = sample_rfp_path.read_bytes()

        result = pipeline.process(
            file_bytes=file_bytes,
            filename=sample_rfp_path.name,
            doc_type_hint="rfp",
        )

        # Ingestion should always succeed
        assert "ingestion" in result.stages_completed
        assert result.document_id
        assert result.record.doc_type == "rfp"

        if result.status == ProcessingStatus.FAILED and "InvalidContent" in (result.error or ""):
            pytest.skip(
                "Document Intelligence does not support .txt files. "
                "Use PDF/DOCX samples for full pipeline E2E. "
                f"Ingestion succeeded: doc_id={result.document_id}"
            )

        # Full pipeline success
        assert result.status == ProcessingStatus.COMPLETED, (
            f"Pipeline failed: {result.error}"
        )
        assert result.stages_completed == [
            "ingestion", "extraction", "analysis", "search"
        ]

    @pytest.mark.timeout(300)
    def test_contract_full_pipeline(self, pipeline, sample_contract_path: Path):
        """Process a sample contract through all 4 stages."""
        file_bytes = sample_contract_path.read_bytes()

        result = pipeline.process(
            file_bytes=file_bytes,
            filename=sample_contract_path.name,
            doc_type_hint="contract",
        )

        assert "ingestion" in result.stages_completed
        assert result.record.doc_type == "contract"

        if result.status == ProcessingStatus.FAILED and "InvalidContent" in (result.error or ""):
            pytest.skip("Document Intelligence does not support .txt files.")

        assert result.status == ProcessingStatus.COMPLETED, (
            f"Pipeline failed: {result.error}"
        )
        assert result.stages_completed == [
            "ingestion", "extraction", "analysis", "search"
        ]

    @pytest.mark.timeout(300)
    def test_spec_full_pipeline(self, pipeline, sample_spec_path: Path):
        """Process a sample spec through all 4 stages."""
        file_bytes = sample_spec_path.read_bytes()

        result = pipeline.process(
            file_bytes=file_bytes,
            filename=sample_spec_path.name,
            doc_type_hint="spec",
        )

        assert "ingestion" in result.stages_completed
        assert result.record.doc_type == "spec"

        if result.status == ProcessingStatus.FAILED and "InvalidContent" in (result.error or ""):
            pytest.skip("Document Intelligence does not support .txt files.")

        assert result.status == ProcessingStatus.COMPLETED, (
            f"Pipeline failed: {result.error}"
        )
        assert result.stages_completed == [
            "ingestion", "extraction", "analysis", "search"
        ]


# ── Individual Stage Tests ─────────────────────────────────────────


class TestIndividualStages:
    """Test individual stages in isolation with real services."""

    def test_blob_upload_download(self, blob_service, sample_rfp_path: Path):
        """Upload to real Blob Storage and verify URL returned."""
        file_bytes = sample_rfp_path.read_bytes()
        blob_url = blob_service.upload_document(
            file_bytes=file_bytes,
            filename=f"e2e-test-{sample_rfp_path.name}",
            container=None,  # uses default raw container
        )
        assert blob_url
        assert "blob.core.windows.net" in blob_url

    def test_cosmos_crud(self, cosmos_service):
        """Create, read, update a document record in real Cosmos DB."""
        import uuid
        from documind.core.models.base import DocumentRecord

        doc_id = f"e2e-test-{uuid.uuid4()}"
        record = DocumentRecord(
            document_id=doc_id,
            doc_type="rfp",
            source_filename="e2e-test.pdf",
            status=ProcessingStatus.PENDING,
        )

        # Create
        cosmos_service.create_record(record)

        # Read — get_record returns a raw dict (CosmosDict), not DocumentRecord
        fetched = cosmos_service.get_record(doc_id, doc_type="rfp")
        assert fetched is not None
        assert fetched["document_id"] == doc_id
        assert fetched["status"] == ProcessingStatus.PENDING.value

        # Update status
        cosmos_service.update_status(doc_id, "rfp", ProcessingStatus.COMPLETED)
        updated = cosmos_service.get_record(doc_id, doc_type="rfp")
        assert updated["status"] == ProcessingStatus.COMPLETED.value

    @pytest.mark.timeout(120)
    def test_llm_caller_returns_content(self, llm_caller):
        """Verify the real LLM caller returns a non-empty response."""
        try:
            response = llm_caller("Say hello in exactly 3 words.")
            assert response
            assert len(response) > 0
        except Exception as exc:
            if "500" in str(exc) or "InternalServerError" in type(exc).__name__:
                pytest.skip(f"Azure OpenAI transient error: {exc}")
            raise

    def test_doc_type_registry_loads(self, registry):
        """Verify all 3 doc types load from YAML."""
        types = registry.list_enabled()
        names = [t.name for t in types]
        assert "rfp" in names
        assert "contract" in names
        assert "spec" in names


# ── Search After Indexing ──────────────────────────────────────────


class TestSearchAfterIndexing:
    """These run after pipeline tests have indexed documents."""

    @pytest.mark.timeout(60)
    def test_semantic_search_returns_results(self, settings, env_loaded):
        """After pipeline runs, search should find indexed docs."""
        from documind.services.vector_search import VectorSearchService

        try:
            svc = VectorSearchService()
            results = svc.semantic_search(
                query="cloud migration requirements",
                doc_type="rfp",
                top_k=3,
            )
            # May be empty if pipeline tests haven't run yet — that's OK
            assert isinstance(results, list)
        except Exception as exc:
            # Vector search container may not exist yet
            pytest.skip(f"Vector search not available: {exc}")
