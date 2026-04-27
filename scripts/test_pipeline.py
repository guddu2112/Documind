"""Quick CLI script to test the DocuMind pipeline end-to-end.

Usage:
    python scripts/test_pipeline.py <path-to-document> [doc_type]

Examples:
    python scripts/test_pipeline.py sample.pdf rfp
    python scripts/test_pipeline.py contract.pdf contract
    python scripts/test_pipeline.py spec.pdf spec
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_pipeline")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    doc_type_hint = sys.argv[2] if len(sys.argv) > 2 else None

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    file_bytes = file_path.read_bytes()
    filename = file_path.name

    print(f"\n{'='*60}")
    print(f"  DocuMind Pipeline Test")
    print(f"  File: {filename} ({len(file_bytes):,} bytes)")
    print(f"  Doc type hint: {doc_type_hint or 'auto-detect'}")
    print(f"{'='*60}\n")

    # ── Build the pipeline ──────────────────────────────────────

    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    from documind.agents.analysis.agent import AnalysisExecutor
    from documind.agents.extraction.agent import ExtractionExecutor
    from documind.agents.ingestion.agent import IngestionExecutor
    from documind.agents.search.agent import SearchExecutor
    from documind.agents.orchestrator.workflow import DocumentPipeline
    from documind.core.config.settings import settings
    from documind.core.tracing import configure_telemetry
    from documind.doctypes.registry import DocTypeRegistry
    from documind.services.blob_storage import BlobStorageService
    from documind.services.cosmos import CosmosService
    from documind.services.document_intelligence import DocumentIntelligenceService
    from documind.services.prompt_loader import PromptLoader
    from documind.services.vector_search import VectorSearchService

    # Set up telemetry
    configure_telemetry(service_name="documind-cli-test")

    registry = DocTypeRegistry()
    registry.load()
    print(f"[OK] Doc-type registry loaded ({len(list(registry.list_enabled()))} types)")

    blob_svc = BlobStorageService()
    print("[OK] Blob Storage connected")

    di_svc = DocumentIntelligenceService()
    print("[OK] Document Intelligence connected")

    cosmos_svc = CosmosService()
    print("[OK] Cosmos DB connected")

    vector_svc = VectorSearchService()
    print("[OK] Vector Search connected")

    prompt_loader = PromptLoader()
    print("[OK] Prompt templates loaded")

    # Build LLM caller
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    oai_client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-12-01-preview",
    )

    def llm_caller(prompt: str) -> str:
        response = oai_client.chat.completions.create(
            model=settings.foundry_model_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    print("[OK] Azure OpenAI connected")

    # Build pipeline
    ingestion = IngestionExecutor(registry=registry, blob_service=blob_svc)
    extraction = ExtractionExecutor(registry=registry, di_service=di_svc)
    analysis = AnalysisExecutor(
        registry=registry,
        prompt_loader=prompt_loader,
        llm_caller=llm_caller,
    )
    search = SearchExecutor(registry=registry, search_service=vector_svc)

    pipeline = DocumentPipeline(
        ingestion=ingestion,
        extraction=extraction,
        analysis=analysis,
        search=search,
        cosmos=cosmos_svc,
    )

    # ── Run the pipeline ────────────────────────────────────────

    print(f"\n{'─'*60}")
    print("Running pipeline...")
    print(f"{'─'*60}\n")

    result = pipeline.process(file_bytes, filename, doc_type_hint=doc_type_hint)

    # ── Print results ───────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"  PIPELINE RESULTS")
    print(f"{'='*60}")
    print(f"  Document ID:      {result.document_id}")
    print(f"  Status:           {result.status.value}")
    print(f"  Stages completed: {', '.join(result.stages_completed)}")

    if result.error:
        print(f"\n  ERROR: {result.error}")

    if result.extraction:
        ext = result.extraction.extraction
        print(f"\n  ── Extraction ──")
        print(f"  Doc type:    {ext.doc_type}")
        print(f"  Pages:       {ext.page_count}")
        print(f"  Confidence:  {ext.confidence_score:.2f}")
        print(f"  KV pairs:    {len(ext.key_value_pairs)}")
        print(f"  Tables:      {len(ext.tables)}")
        print(f"  Text length: {len(ext.raw_text):,} chars")
        if ext.key_value_pairs:
            print(f"\n  Key-Value Pairs:")
            for kv in ext.key_value_pairs[:10]:
                print(f"    {kv.key}: {kv.value} (conf: {kv.confidence:.2f})")

    if result.analysis:
        ana = result.analysis.analysis
        print(f"\n  ── Analysis ──")
        print(f"  Summary:")
        # Wrap summary at 70 chars
        summary = ana.summary
        for i in range(0, len(summary), 70):
            prefix = "    " if i == 0 else "             "
            print(f"{prefix}{summary[i:i+70]}")
        if ana.risks:
            print(f"\n  Risks ({len(ana.risks)}):")
            for risk in ana.risks:
                print(f"    [{risk.severity.value.upper()}] {risk.title}")
                print(f"      {risk.description[:80]}")
                if risk.recommendation:
                    print(f"      → {risk.recommendation[:80]}")

    print(f"\n{'='*60}")
    print("Done!")

    # Cleanup test file
    test_file = Path("test_sample.txt")
    if test_file.exists():
        test_file.unlink()


if __name__ == "__main__":
    main()
