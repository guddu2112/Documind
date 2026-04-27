"""Ingestion Agent — workflow executor.

This executor is the entry point of the DocuMind pipeline.  It:

1. Classifies the incoming document's type using the doc-type registry.
2. Creates a ``DocumentRecord`` in PENDING status.
3. Uploads the raw file to Azure Blob Storage.
4. Forwards the record (with blob URL) to the next executor.

The executor follows the Microsoft Agent Framework ``Executor`` pattern
so it can be wired into a ``WorkflowBuilder`` pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from documind.agents.ingestion.tools.tools import (
    classify_doc_type,
    store_to_blob,
    upload_document,
)
from documind.core.models.base import DocumentRecord
from documind.doctypes.registry import DocTypeRegistry
from documind.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)


@dataclass
class IngestionInput:
    """Input payload for the Ingestion Executor.

    Encapsulates everything needed to start processing a document.
    """
    file_bytes: bytes
    filename: str
    doc_type_hint: str | None = None  # optional user-supplied hint
    document_id: str | None = None    # pre-assigned ID (from API layer)


@dataclass
class IngestionOutput:
    """Output produced by the Ingestion Executor.

    Passed downstream to the Extraction Executor.
    """
    record: DocumentRecord
    file_bytes: bytes  # kept in memory for extraction (avoids a re-download)


class IngestionExecutor:
    """Ingestion workflow step — classify, create record, upload to blob.

    This class is designed as a plain Python class so it can be tested
    without the Agent Framework SDK.  When wired into the Orchestrator,
    it is wrapped in an ``AgentExecutor`` or called from a ``@handler``.
    """

    def __init__(
        self,
        registry: DocTypeRegistry,
        blob_service: BlobStorageService,
    ) -> None:
        self._registry = registry
        self._blob_service = blob_service

    def run(self, inp: IngestionInput) -> IngestionOutput:
        """Execute the ingestion step synchronously.

        Returns an ``IngestionOutput`` containing the document record
        and the raw file bytes for the next stage.
        """
        # Step 1 — Determine doc type
        doc_config = classify_doc_type(
            filename=inp.filename,
            registry=self._registry,
            hint=inp.doc_type_hint,
        )

        # Step 2 — Create a tracking record
        record = upload_document(
            file_bytes=inp.file_bytes,
            filename=inp.filename,
            doc_type=doc_config.name,
            document_id=inp.document_id,
        )

        # Step 3 — Persist to blob storage
        store_to_blob(
            file_bytes=inp.file_bytes,
            record=record,
            blob_service=self._blob_service,
        )

        logger.info(
            "Ingestion complete: id=%s type=%s blob=%s",
            record.document_id,
            record.doc_type,
            record.blob_url,
        )
        return IngestionOutput(record=record, file_bytes=inp.file_bytes)
