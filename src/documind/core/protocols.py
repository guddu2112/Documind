"""Service Protocols — abstract interfaces for multi-cloud portability.

Each protocol mirrors the public API of its Azure-based concrete
implementation.  Pipeline stages and executors should type-hint against
these protocols so a different cloud's service can be swapped in without
touching business logic.

Example — to port to AWS::

    class S3StorageService:  # implements StorageProtocol
        def upload_document(self, ...) -> str: ...

    pipeline = DocumentPipeline(
        ingestion=IngestionExecutor(storage=S3StorageService()),
        ...
    )
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from documind.core.models.base import (
    DocumentRecord,
    ExtractedTable,
    KeyValuePair,
    ProcessingStatus,
)


# ── Storage ─────────────────────────────────────────────────────


@runtime_checkable
class StorageProtocol(Protocol):
    """Blob / object storage — upload, download, list."""

    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        container: str | None = None,
        document_id: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str: ...

    def download_document(self, container: str, blob_path: str) -> bytes: ...

    def list_blobs(self, container: str, prefix: str = "") -> list[str]: ...


# ── Document Extraction ─────────────────────────────────────────


@runtime_checkable
class DocumentExtractorProtocol(Protocol):
    """Document intelligence / OCR — analyse, extract text, tables, KVPs."""

    def analyze_document(
        self,
        file_bytes: bytes,
        model_id: str = "prebuilt-layout",
    ) -> dict[str, Any]: ...

    def extract_text(self, analysis_result: Any) -> str: ...

    def extract_key_value_pairs(self, analysis_result: Any) -> list[KeyValuePair]: ...

    def extract_tables(self, analysis_result: Any) -> list[ExtractedTable]: ...

    def get_page_count(self, analysis_result: Any) -> int: ...


# ── LLM ─────────────────────────────────────────────────────────


@runtime_checkable
class LLMProtocol(Protocol):
    """Callable that accepts a prompt and returns the LLM's text response."""

    def __call__(self, prompt: str) -> str: ...


# ── Search / Vector Search ──────────────────────────────────────


@runtime_checkable
class SearchProtocol(Protocol):
    """Document indexing + semantic & faceted search."""

    def index_document(self, document: dict[str, Any]) -> dict[str, Any]: ...

    def semantic_search(
        self,
        query: str,
        top: int = 5,
        filters: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def faceted_search(
        self,
        query: str,
        facets: list[str],
        top: int = 10,
    ) -> dict[str, Any]: ...


# ── State Store ─────────────────────────────────────────────────


@runtime_checkable
class StateStoreProtocol(Protocol):
    """Document record persistence (pipeline state, metadata)."""

    def create_record(self, record: DocumentRecord) -> dict[str, Any]: ...

    def get_record(self, document_id: str, doc_type: str) -> dict[str, Any]: ...

    def upsert_record(self, record: DocumentRecord) -> dict[str, Any]: ...

    def update_status(
        self,
        document_id: str,
        doc_type: str,
        status: ProcessingStatus,
        **extra_fields: Any,
    ) -> dict[str, Any]: ...

    def query_by_status(
        self,
        status: ProcessingStatus,
        max_items: int = 50,
    ) -> list[dict[str, Any]]: ...
