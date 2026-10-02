"""Filesystem blob store — offline replacement for ``BlobStorageService``.

Persists uploads under ``<local_blob_dir>/<container>/<document_id>/<filename>``
so the layout matches the Azure Blob path convention used elsewhere.

Public interface mirrors ``BlobStorageService`` exactly:
    - upload_document, download_document, list_blobs
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


class LocalBlobStorage:
    """Blob storage backed by the local filesystem."""

    def __init__(self, root_dir: str | None = None) -> None:
        self._root = Path(root_dir or settings.local_blob_dir).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("LocalBlobStorage ready at %s", self._root)

    # ── Internal ───────────────────────────────────────────────

    def _container_dir(self, container: str) -> Path:
        d = self._root / container
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── BlobStorageService-compatible API ──────────────────────

    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        container: Optional[str] = None,
        document_id: Optional[str] = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        container = container or settings.azure_storage_container_raw
        document_id = document_id or str(uuid.uuid4())

        target = self._container_dir(container) / document_id / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)

        logger.info("Wrote %s (%d bytes) to %s", filename, len(file_bytes), target)
        return target.as_uri()

    def download_document(self, container: str, blob_path: str) -> bytes:
        path = self._container_dir(container) / blob_path
        if not path.is_file():
            raise FileNotFoundError(f"Blob not found: {container}/{blob_path}")
        return path.read_bytes()

    def list_blobs(self, container: str, prefix: str = "") -> list[str]:
        base = self._container_dir(container)
        names: list[str] = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            if rel.startswith(prefix):
                names.append(rel)
        return names
