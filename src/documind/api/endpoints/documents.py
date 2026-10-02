"""Document endpoints — upload, status, and analysis retrieval.

Routes:
    POST   /documents           — Upload a document and start processing.
    GET    /documents/{id}      — Get processing status.
    GET    /documents/{id}/analysis — Get full analysis results.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from documind.api.schemas import (
    AnalysisResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from documind.core.models.base import ProcessingStatus

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────


def _build_pipeline():
    """Construct a DocumentPipeline with real services.

    Deferred import so the module can be loaded without triggering
    Azure SDK connections at import time.
    """
    from documind.agents.analysis.agent import AnalysisExecutor
    from documind.agents.extraction.agent import ExtractionExecutor
    from documind.agents.ingestion.agent import IngestionExecutor
    from documind.agents.search.agent import SearchExecutor
    from documind.agents.orchestrator.workflow import DocumentPipeline
    from documind.doctypes.registry import DocTypeRegistry
    from documind.services import factory
    from documind.services.prompt_loader import PromptLoader

    registry = DocTypeRegistry()
    registry.load()

    blob_svc = factory.get_blob_store()
    di_svc = factory.get_extractor()
    cosmos_svc = factory.get_record_store()
    vector_svc = factory.get_search_service()
    llm_caller = factory.get_llm_caller()
    prompt_loader = PromptLoader()

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


def _run_pipeline_background(
    file_bytes: bytes,
    filename: str,
    doc_type: str | None,
    document_id: str,
) -> None:
    """Execute the pipeline in a background thread.

    Called via FastAPI BackgroundTasks so the upload endpoint returns
    immediately.
    """
    import traceback
    import sys

    try:
        logger.info("Starting pipeline for document %s (%s)", document_id, filename)
        print(f"[DOCUMIND] Starting pipeline for {document_id} ({filename})", file=sys.stderr, flush=True)
        pipeline = _build_pipeline()
        result = pipeline.process(file_bytes, filename, doc_type_hint=doc_type, document_id=document_id)
        logger.info(
            "Pipeline finished for %s: status=%s stages=%s",
            document_id,
            result.status.value,
            result.stages_completed,
        )
        print(f"[DOCUMIND] Pipeline finished for {document_id}: status={result.status.value}", file=sys.stderr, flush=True)
    except Exception:
        logger.exception("Pipeline background task failed for %s", document_id)
        traceback.print_exc(file=sys.stderr)
        # Also update Cosmos record to FAILED so status endpoint can report it
        try:
            from documind.services import factory
            cosmos = factory.get_record_store()
            cosmos.update_status(document_id, doc_type or "unknown", ProcessingStatus.FAILED)
        except Exception:
            logger.warning("Could not update Cosmos status to FAILED for %s", document_id)


# ── Endpoints ──────────────────────────────────────────────────────


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=202,
    summary="Upload a document for processing",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX, or image file"),
    doc_type: str = Form("auto", description="Document type hint (rfp, contract, spec) or 'auto'"),
):
    """Accept a document upload and enqueue it for processing.

    Returns immediately with a 202 and the assigned ``document_id``.
    The pipeline runs in the background.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename is required.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    document_id = str(uuid.uuid4())
    doc_type_hint = doc_type if doc_type != "auto" else None
    effective_doc_type = doc_type if doc_type != "auto" else "pending"

    # Create an initial PENDING record in Cosmos so the status endpoint
    # can find this document immediately (before the pipeline runs).
    try:
        from documind.services import factory
        from documind.core.models.base import DocumentRecord

        cosmos = factory.get_record_store()
        initial_record = DocumentRecord(
            document_id=document_id,
            doc_type=effective_doc_type,
            source_filename=file.filename,
            status=ProcessingStatus.PENDING,
        )
        cosmos.create_record(initial_record)
        logger.info("Created pending record for %s (partition=%s)", document_id, effective_doc_type)
    except Exception as exc:
        # Print to stderr as failsafe — logging may be silenced by uvicorn
        import sys
        print(f"[DOCUMIND ERROR] Failed to create record for {document_id}: {exc}", file=sys.stderr, flush=True)
        logger.exception("Failed to create initial record for %s", document_id)

    background_tasks.add_task(
        _run_pipeline_background,
        file_bytes,
        file.filename,
        doc_type_hint,
        document_id,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        doc_type=effective_doc_type,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
)
async def get_document_status(document_id: str, doc_type: str | None = None):
    """Retrieve the current processing status for a document."""
    from documind.services import factory

    cosmos = factory.get_record_store()
    record = None

    # Skip point-read on the "pending" placeholder partition — the real row lives under the classified doc_type.
    if doc_type and doc_type != "pending":
        try:
            record = cosmos.get_record(document_id, doc_type)
        except Exception:
            pass

    if record is None:
        try:
            record = cosmos.query_by_document_id(document_id)
        except Exception:
            pass

    if record is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return DocumentStatusResponse(
        document_id=record["document_id"],
        doc_type=record["doc_type"],
        status=record["status"],
        filename=record.get("source_filename", ""),
        uploaded_at=record.get("uploaded_at"),
        completed_at=record.get("completed_at"),
        error_message=record.get("error_message"),
        stages_completed=record.get("stages_completed", []),
    )


@router.get(
    "/{document_id}/analysis",
    response_model=AnalysisResponse,
    summary="Get full analysis results",
)
async def get_document_analysis(document_id: str, doc_type: str | None = None):
    """Retrieve extraction and analysis results for a processed document."""
    from documind.services import factory

    cosmos = factory.get_record_store()
    record = None

    if doc_type and doc_type != "pending":
        try:
            record = cosmos.get_record(document_id, doc_type)
        except Exception:
            pass

    if record is None:
        try:
            record = cosmos.query_by_document_id(document_id)
        except Exception:
            pass

    if record is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    if record["status"] != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Document is not yet processed (status: {record['status']}).",
        )

    return AnalysisResponse(
        document_id=record["document_id"],
        doc_type=record["doc_type"],
        status=record["status"],
        extraction=record.get("extraction"),
        analysis=record.get("analysis"),
    )
