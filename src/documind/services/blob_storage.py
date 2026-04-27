"""Azure Blob Storage service wrapper.

Provides async helpers for uploading and downloading documents.  All
methods accept an optional ``BlobServiceClient`` so callers (and tests)
can inject their own client instance.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContentSettings

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


def _default_client() -> BlobServiceClient:
    """Build a BlobServiceClient from settings.

    Prefers connection string; falls back to DefaultAzureCredential +
    account name for managed-identity deployments.
    """
    if settings.azure_storage_connection_string:
        return BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
    # Managed-identity path
    from azure.identity import DefaultAzureCredential

    account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=DefaultAzureCredential())


class BlobStorageService:
    """Thin wrapper around Azure Blob Storage SDK."""

    def __init__(self, client: Optional[BlobServiceClient] = None) -> None:
        # Allow dependency injection for testability
        self._client = client or _default_client()

    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        container: str | None = None,
        document_id: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a document to blob storage and return the blob URL.

        The blob is stored under ``<document_id>/<filename>`` so each
        document gets its own virtual directory.
        """
        container = container or settings.azure_storage_container_raw
        document_id = document_id or str(uuid.uuid4())

        # Use <document_id>/<filename> as the blob path for easy grouping
        blob_path = f"{document_id}/{filename}"

        blob_client = self._client.get_blob_client(
            container=container, blob=blob_path
        )
        blob_client.upload_blob(
            file_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        logger.info("Uploaded %s to %s/%s", filename, container, blob_path)
        return blob_client.url

    def download_document(self, container: str, blob_path: str) -> bytes:
        """Download a blob and return its bytes."""
        blob_client = self._client.get_blob_client(
            container=container, blob=blob_path
        )
        return blob_client.download_blob().readall()

    def list_blobs(self, container: str, prefix: str = "") -> list[str]:
        """List blob names in *container* matching *prefix*."""
        container_client = self._client.get_container_client(container)
        return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]
