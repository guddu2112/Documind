"""Azure Cosmos DB service wrapper.

Manages document records (pipeline state, metadata, audit trail) in a
serverless Cosmos DB container.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from documind.core.config.settings import settings
from documind.core.models.base import DocumentRecord, ProcessingStatus

logger = logging.getLogger(__name__)


def _default_client():
    """Build a CosmosClient from settings."""
    from azure.cosmos import CosmosClient

    if settings.azure_cosmos_key:
        return CosmosClient(settings.azure_cosmos_endpoint, settings.azure_cosmos_key)
    from azure.identity import DefaultAzureCredential
    return CosmosClient(settings.azure_cosmos_endpoint, DefaultAzureCredential())


class CosmosService:
    """CRUD operations for document records in Cosmos DB."""

    def __init__(self, client=None) -> None:
        self._client = client or _default_client()
        self._database_name = settings.azure_cosmos_database
        self._container_name = settings.azure_cosmos_container

    @property
    def _container(self):
        """Lazy reference to the Cosmos container."""
        db = self._client.get_database_client(self._database_name)
        return db.get_container_client(self._container_name)

    def create_record(self, record: DocumentRecord) -> dict[str, Any]:
        """Insert a new document record.

        Cosmos requires an ``id`` field; we use ``document_id`` for that.
        The partition key path is ``/documentType`` (camelCase, from Terraform).
        """
        body = record.model_dump(mode="json")
        body["id"] = record.document_id  # Cosmos primary key
        body["documentType"] = record.doc_type  # Partition key field
        result = self._container.create_item(body=body)
        logger.info("Created record %s (type=%s)", record.document_id, record.doc_type)
        return result

    def get_record(self, document_id: str, doc_type: str) -> dict[str, Any]:
        """Read a single document record by id and partition key."""
        return self._container.read_item(item=document_id, partition_key=doc_type)

    def upsert_record(self, record: DocumentRecord) -> dict[str, Any]:
        """Insert or replace a document record."""
        body = record.model_dump(mode="json")
        body["id"] = record.document_id
        body["documentType"] = record.doc_type
        result = self._container.upsert_item(body=body)
        logger.info("Upserted record %s (type=%s)", record.document_id, record.doc_type)
        return result

    def update_status(
        self,
        document_id: str,
        doc_type: str,
        status: ProcessingStatus,
        **extra_fields,
    ) -> dict[str, Any]:
        """Update the processing status (and any extra fields) on a record.

        Uses a full replace under the hood because Cosmos doesn't support
        partial patch in all SDK versions.
        """
        item = self.get_record(document_id, doc_type)
        item["status"] = status.value
        item.update(extra_fields)
        result = self._container.replace_item(item=document_id, body=item)
        logger.info("Updated %s → %s", document_id, status.value)
        return result

    def query_by_status(
        self, status: ProcessingStatus, max_items: int = 50
    ) -> list[dict[str, Any]]:
        """Find all records with a given processing status."""
        query = "SELECT * FROM c WHERE c.status = @status"
        params = [{"name": "@status", "value": status.value}]
        return list(
            self._container.query_items(
                query=query, parameters=params, max_item_count=max_items
            )
        )
