"""Extraction Agent — workflow executor.

Receives an ``IngestionOutput`` (document record + raw bytes) from the
Ingestion Executor and runs Azure Document Intelligence to produce an
``ExtractionResult``.

The model ID used for analysis is determined by the doc-type config, so
different document types can use different Document Intelligence models
(e.g. ``prebuilt-layout`` for specs, ``prebuilt-contract`` for contracts).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from documind.agents.extraction.tools.tools import (
    build_extraction_result,
    extract_layout,
)
from documind.agents.ingestion.agent import IngestionOutput
from documind.core.models.base import ExtractionResult
from documind.doctypes.registry import DocTypeRegistry
from documind.services.document_intelligence import DocumentIntelligenceService

logger = logging.getLogger(__name__)


@dataclass
class ExtractionOutput:
    """Output produced by the Extraction Executor.

    Contains the extraction result plus the ingestion output for
    reference by downstream stages.
    """
    extraction: ExtractionResult
    ingestion: IngestionOutput  # carry forward for analysis


class ExtractionExecutor:
    """Extraction workflow step — run Document Intelligence and parse results."""

    def __init__(
        self,
        registry: DocTypeRegistry,
        di_service: DocumentIntelligenceService,
    ) -> None:
        self._registry = registry
        self._di_service = di_service

    def run(self, inp: IngestionOutput) -> ExtractionOutput:
        """Execute extraction on the ingested document.

        1. Look up the Document Intelligence model from the doc-type config.
        2. Call the Document Intelligence SDK via ``extract_layout``.
        3. Parse the result into an ``ExtractionResult``.
        """
        # Get the doc-type config to find which DI model to use
        doc_config = self._registry.get(inp.record.doc_type)
        model_id = doc_config.doc_intelligence_model

        # Step 1 — Run Document Intelligence
        analysis_result = extract_layout(
            file_bytes=inp.file_bytes,
            model_id=model_id,
            di_service=self._di_service,
        )

        # Step 2 — Build the structured extraction result
        extraction = build_extraction_result(
            document_id=inp.record.document_id,
            doc_type=inp.record.doc_type,
            source_filename=inp.record.source_filename,
            analysis_result=analysis_result,
            di_service=self._di_service,
        )

        logger.info(
            "Extraction complete: id=%s pages=%d kv_pairs=%d tables=%d",
            extraction.document_id,
            extraction.page_count,
            len(extraction.key_value_pairs),
            len(extraction.tables),
        )
        return ExtractionOutput(extraction=extraction, ingestion=inp)
