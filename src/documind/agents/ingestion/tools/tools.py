"""Ingestion Agent function tools.

These are standalone functions that handle the three steps of document
ingestion:

1. **classify_doc_type** — determine which doc-type config applies
2. **upload_document**   — validate file and assign a document ID
3. **store_to_blob**     — persist the raw file in Azure Blob Storage

Each function is independent and testable without the Agent Framework.
The IngestionExecutor composes them into a single workflow step.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path

from documind.core.models.base import DocumentRecord, ProcessingStatus
from documind.doctypes.registry import DocTypeRegistry
from documind.doctypes.schema import DocumentTypeConfig, SupportedFormat
from documind.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

# Map common MIME types / extensions to our SupportedFormat enum values
_EXTENSION_MAP: dict[str, SupportedFormat] = {
    ".pdf": SupportedFormat.PDF,
    ".docx": SupportedFormat.DOCX,
    ".xlsx": SupportedFormat.XLSX,
    ".pptx": SupportedFormat.PPTX,
    ".png": SupportedFormat.PNG,
    ".jpg": SupportedFormat.JPG,
    ".jpeg": SupportedFormat.JPG,
    ".tiff": SupportedFormat.TIFF,
    ".tif": SupportedFormat.TIFF,
    ".txt": SupportedFormat.TXT,
    ".md": SupportedFormat.MD,
}


def classify_doc_type(
    filename: str,
    registry: DocTypeRegistry,
    hint: str | None = None,
) -> DocumentTypeConfig:
    """Determine the document type for the uploaded file.

    Strategy:
    1. If a *hint* is provided (e.g. from a dropdown), use it directly.
    2. Otherwise, check the file extension against each registered
       doc type's ``supported_formats`` and return the first match.
    3. If no doc type matches, raise ``ValueError``.

    In Phase 4 this can be upgraded to an LLM-based classifier that
    reads the first page of the document.
    """
    # 1) Explicit hint — fastest path
    if hint and hint in registry:
        config = registry.get(hint)
        logger.info("Doc type resolved via hint: %s", config.name)
        return config

    # 2) Extension-based matching
    ext = Path(filename).suffix.lower()
    fmt = _EXTENSION_MAP.get(ext)
    if fmt is None:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Accepted: {list(_EXTENSION_MAP.keys())}"
        )

    # Find the first enabled doc type that accepts this format
    for config in registry.list_enabled():
        if fmt in config.supported_formats:
            logger.info(
                "Doc type resolved via extension %s → %s", ext, config.name
            )
            return config

    raise ValueError(
        f"No enabled doc type accepts format '{fmt.value}'. "
        "Register a doc type that supports this format."
    )


def upload_document(
    file_bytes: bytes,
    filename: str,
    doc_type: str,
    document_id: str | None = None,
) -> DocumentRecord:
    """Validate the upload and create an initial DocumentRecord.

    The record starts in PENDING status.  The actual blob upload happens
    in ``store_to_blob`` so the two steps can be tested independently.
    """
    if not file_bytes:
        raise ValueError("File is empty — nothing to upload.")
    if not filename:
        raise ValueError("Filename is required.")

    document_id = document_id or str(uuid.uuid4())

    # Guess MIME type for later use in blob upload
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"

    record = DocumentRecord(
        document_id=document_id,
        doc_type=doc_type,
        source_filename=filename,
        status=ProcessingStatus.PENDING,
    )
    logger.info(
        "Created document record id=%s type=%s file=%s (%d bytes)",
        document_id,
        doc_type,
        filename,
        len(file_bytes),
    )
    return record


def store_to_blob(
    file_bytes: bytes,
    record: DocumentRecord,
    blob_service: BlobStorageService,
) -> str:
    """Upload the raw document to Azure Blob Storage.

    Returns the blob URL which is stored on the DocumentRecord for
    downstream agents to retrieve the file.
    """
    content_type, _ = mimetypes.guess_type(record.source_filename)
    content_type = content_type or "application/octet-stream"

    blob_url = blob_service.upload_document(
        file_bytes=file_bytes,
        filename=record.source_filename,
        document_id=record.document_id,
        content_type=content_type,
    )
    # Update the record in place so the caller has the URL
    record.blob_url = blob_url
    logger.info("Stored blob for %s → %s", record.document_id, blob_url)
    return blob_url
