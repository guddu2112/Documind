"""SQLite-backed record store — offline replacement for ``CosmosService``.

Stores ``DocumentRecord`` instances as JSON blobs in a single SQLite file
so the API and pipeline can share pipeline state without a cloud
database.

Public interface mirrors ``CosmosService`` exactly:
    - create_record, get_record, upsert_record, update_status, query_by_status

Plus one method the offline events endpoint needs (Cosmos does the same
via a cross-partition query):
    - query_by_document_id
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from documind.core.config.settings import settings
from documind.core.models.base import DocumentRecord, ProcessingStatus

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    document_id  TEXT NOT NULL,
    doc_type     TEXT NOT NULL,
    status       TEXT NOT NULL,
    body         TEXT NOT NULL,
    updated_at   REAL NOT NULL DEFAULT (julianday('now')),
    PRIMARY KEY (document_id, doc_type)
);
CREATE INDEX IF NOT EXISTS idx_records_status ON records(status);
CREATE INDEX IF NOT EXISTS idx_records_docid  ON records(document_id);
"""


class SQLiteRecordStore:
    """Document-record persistence backed by a local SQLite file."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = str(Path(db_path or settings.sqlite_path).expanduser().resolve())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        # SQLite connection sharing across threads is unsafe by default;
        # we serialize writes with a lock and open with check_same_thread=False.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn.executescript(_SCHEMA)
        logger.info("SQLiteRecordStore ready at %s", self._db_path)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _to_body(record: DocumentRecord) -> dict[str, Any]:
        body = record.model_dump(mode="json")
        body["id"] = record.document_id
        body["documentType"] = record.doc_type
        return body

    def _write(self, record: DocumentRecord) -> dict[str, Any]:
        body = self._to_body(record)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO records "
                "(document_id, doc_type, status, body, updated_at) "
                "VALUES (?, ?, ?, ?, julianday('now'))",
                (record.document_id, record.doc_type, record.status.value, json.dumps(body)),
            )
        return body

    # ── CosmosService-compatible API ───────────────────────────

    def create_record(self, record: DocumentRecord) -> dict[str, Any]:
        result = self._write(record)
        logger.info("Created record %s (type=%s)", record.document_id, record.doc_type)
        return result

    def upsert_record(self, record: DocumentRecord) -> dict[str, Any]:
        result = self._write(record)
        logger.info("Upserted record %s (type=%s)", record.document_id, record.doc_type)
        return result

    def get_record(self, document_id: str, doc_type: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT body FROM records WHERE document_id = ? AND doc_type = ?",
                (document_id, doc_type),
            ).fetchone()
        if row is None:
            raise KeyError(f"Record not found: id={document_id}, doc_type={doc_type}")
        return json.loads(row[0])

    def update_status(
        self,
        document_id: str,
        doc_type: str,
        status: ProcessingStatus,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        item = self.get_record(document_id, doc_type)
        item["status"] = status.value
        item.update(extra_fields)
        with self._lock:
            self._conn.execute(
                "UPDATE records SET status = ?, body = ?, updated_at = julianday('now') "
                "WHERE document_id = ? AND doc_type = ?",
                (status.value, json.dumps(item), document_id, doc_type),
            )
        logger.info("Updated %s → %s", document_id, status.value)
        return item

    def query_by_status(
        self, status: ProcessingStatus, max_items: int = 50
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT body FROM records WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status.value, max_items),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Extra: partition-key-free lookup for events.py ─────────

    def query_by_document_id(self, document_id: str) -> Optional[dict[str, Any]]:
        """Return the record (or None) without needing the doc_type partition."""
        # Prefer the classified row over the placeholder "pending" row, then latest update.
        with self._lock:
            row = self._conn.execute(
                "SELECT body FROM records WHERE document_id = ? "
                "ORDER BY (doc_type = 'pending') ASC, updated_at DESC LIMIT 1",
                (document_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
