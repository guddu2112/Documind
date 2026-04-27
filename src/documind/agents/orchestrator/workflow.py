"""Orchestrator — sequential document processing pipeline.

Coordinates the four agents in a deterministic sequence:

    Ingest → Extract → Analyze → Index

This module provides two execution modes:

1. **``DocumentPipeline``** — a plain Python class that runs the pipeline
   synchronously.  Used for testing, CLI, and simple deployments.

2. **Agent Framework integration** — (Phase 2) wraps each executor in a
   ``WorkflowBuilder`` graph using the ``agent_framework`` SDK for
   streaming, retry, and hosted deployment via Microsoft Foundry.

The pipeline tracks status in Cosmos DB at each step so failures can
be retried from the last successful stage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from documind.agents.analysis.agent import AnalysisExecutor, AnalysisOutput
from documind.agents.extraction.agent import ExtractionExecutor, ExtractionOutput
from documind.agents.ingestion.agent import (
    IngestionExecutor,
    IngestionInput,
    IngestionOutput,
)
from documind.agents.search.agent import SearchExecutor, SearchOutput
from documind.core.models.base import DocumentRecord, ProcessingStatus
from documind.services.cosmos import CosmosService

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Final result of the full document processing pipeline."""
    document_id: str
    status: ProcessingStatus
    record: DocumentRecord
    extraction: Optional[ExtractionOutput] = None
    analysis: Optional[AnalysisOutput] = None
    search: Optional[SearchOutput] = None
    error: Optional[str] = None
    stages_completed: list[str] = field(default_factory=list)


class DocumentPipeline:
    """Orchestrates the full Ingest → Extract → Analyze → Index pipeline.

    Each stage is a separate executor instance, injected at construction
    time for testability.  The pipeline catches exceptions at each stage
    so partial results are preserved and failures are logged.

    Usage::

        pipeline = DocumentPipeline(
            ingestion=ingestion_executor,
            extraction=extraction_executor,
            analysis=analysis_executor,
            search=search_executor,
            cosmos=cosmos_service,  # optional — for status tracking
        )
        result = pipeline.process(file_bytes, filename)
    """

    def __init__(
        self,
        ingestion: IngestionExecutor,
        extraction: ExtractionExecutor,
        analysis: AnalysisExecutor,
        search: SearchExecutor,
        cosmos: Optional[CosmosService] = None,
    ) -> None:
        self._ingestion = ingestion
        self._extraction = extraction
        self._analysis = analysis
        self._search = search
        self._cosmos = cosmos

    def process(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type_hint: str | None = None,
        document_id: str | None = None,
    ) -> PipelineResult:
        """Run the full pipeline on a single document.

        Returns a ``PipelineResult`` with the status and all intermediate
        outputs.  If a stage fails, the pipeline stops and records the
        error — earlier stages' results are still available.
        """
        result = PipelineResult(
            document_id="",
            status=ProcessingStatus.PENDING,
            record=DocumentRecord(
                document_id="", doc_type="", source_filename=filename,
            ),
        )

        logger.info("▶ PIPELINE START: file=%s hint=%s id=%s", filename, doc_type_hint, document_id)

        # ── Stage 1: Ingestion ──────────────────────────────────────
        try:
            logger.info("▶ Stage 1/4: INGESTION starting")
            ingestion_input = IngestionInput(
                file_bytes=file_bytes,
                filename=filename,
                doc_type_hint=doc_type_hint,
                document_id=document_id,
            )
            ingestion_out = self._ingestion.run(ingestion_input)
            result.document_id = ingestion_out.record.document_id
            result.record = ingestion_out.record
            result.stages_completed.append("ingestion")
            logger.info("✔ Stage 1/4: INGESTION complete — doc_id=%s doc_type=%s blob=%s",
                        result.document_id, result.record.doc_type, result.record.blob_url)

            # Persist initial record in Cosmos if available
            self._update_status(result.record, ProcessingStatus.EXTRACTING)

        except Exception as exc:
            return self._fail(result, "ingestion", exc)

        # ── Stage 2: Extraction ─────────────────────────────────────
        try:
            logger.info("▶ Stage 2/4: EXTRACTION starting")
            result.record.status = ProcessingStatus.EXTRACTING
            extraction_out = self._extraction.run(ingestion_out)
            result.extraction = extraction_out
            result.record.extraction = extraction_out.extraction
            result.stages_completed.append("extraction")
            logger.info("✔ Stage 2/4: EXTRACTION complete — pages=%s text_len=%s",
                        getattr(extraction_out, 'page_count', '?'),
                        len(getattr(extraction_out, 'text', '') or ''))

            self._update_status(result.record, ProcessingStatus.ANALYZING)

        except Exception as exc:
            return self._fail(result, "extraction", exc)

        # ── Stage 3: Analysis ───────────────────────────────────────
        try:
            logger.info("▶ Stage 3/4: ANALYSIS starting")
            result.record.status = ProcessingStatus.ANALYZING
            analysis_out = self._analysis.run(extraction_out)
            result.analysis = analysis_out
            result.record.analysis = analysis_out.analysis
            result.stages_completed.append("analysis")
            logger.info("✔ Stage 3/4: ANALYSIS complete — summary_len=%s",
                        len(getattr(analysis_out, 'summary', '') or ''))

            self._update_status(result.record, ProcessingStatus.INDEXING)

        except Exception as exc:
            return self._fail(result, "analysis", exc)

        # ── Stage 4: Search Indexing ────────────────────────────────
        try:
            logger.info("▶ Stage 4/4: SEARCH INDEXING starting")
            result.record.status = ProcessingStatus.INDEXING
            search_out = self._search.run(analysis_out)
            result.search = search_out
            result.stages_completed.append("search")

            # Pipeline complete
            result.status = ProcessingStatus.COMPLETED
            result.record.status = ProcessingStatus.COMPLETED
            result.record.completed_at = datetime.utcnow()
            logger.info("✔ Stage 4/4: SEARCH INDEXING complete")

            self._update_status(result.record, ProcessingStatus.COMPLETED)

        except Exception as exc:
            return self._fail(result, "search", exc)

        logger.info(
            "✔ PIPELINE COMPLETE: id=%s stages=%s",
            result.document_id,
            result.stages_completed,
        )
        return result

    def _fail(
        self,
        result: PipelineResult,
        stage: str,
        exc: Exception,
    ) -> PipelineResult:
        """Record a stage failure and return the partial result."""
        result.status = ProcessingStatus.FAILED
        result.error = f"Failed at {stage}: {exc}"
        result.record.status = ProcessingStatus.FAILED
        result.record.error_message = result.error
        logger.error("✘ PIPELINE FAILED at %s: %s", stage, exc, exc_info=True)

        self._update_status(result.record, ProcessingStatus.FAILED)
        return result

    def _update_status(
        self, record: DocumentRecord, status: ProcessingStatus
    ) -> None:
        """Update status in Cosmos DB if the service is available.

        This is a best-effort operation — if Cosmos is unavailable, the
        pipeline continues (the record is still in memory).
        """
        if self._cosmos is None:
            return
        try:
            record.status = status
            self._cosmos.upsert_record(record)
        except Exception:
            logger.warning(
                "Could not update Cosmos status for %s", record.document_id,
                exc_info=True,
            )
