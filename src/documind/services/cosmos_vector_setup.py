"""Cosmos DB container setup for vector search.

This module creates (or validates) the Cosmos DB container that stores
search documents with vector embeddings.  It's run once during
deployment or application startup.

The container uses:
    - **Partition key**: ``/doc_type`` (same as the documents container).
    - **Vector embedding policy**: DiskANN index on the ``embedding`` field.
    - **Composite indexes**: For efficient filtered + sorted queries.

Usage::

    from documind.services.cosmos_vector_setup import ensure_search_container

    ensure_search_container()  # idempotent — safe to call on every startup
"""

from __future__ import annotations

import logging
from typing import Any

from documind.core.config.settings import settings
from documind.services.vector_search import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


def ensure_search_container(
    client=None,
    database_name: str | None = None,
    container_name: str | None = None,
) -> None:
    """Create the vector search container if it doesn't exist.

    Uses Cosmos DB's vector embedding policy to enable DiskANN indexing
    on the ``embedding`` field.  The container is created with serverless
    throughput (no provisioned RUs — pay-per-request only).

    This function is idempotent — calling it when the container already
    exists is a no-op.

    Args:
        client:         Optional CosmosClient instance (for testing).
        database_name:  Database name (defaults to settings).
        container_name: Container name (defaults to settings.cosmos_search_container).
    """
    if client is None:
        from azure.cosmos import CosmosClient

        if settings.azure_cosmos_key:
            client = CosmosClient(settings.azure_cosmos_endpoint, settings.azure_cosmos_key)
        else:
            from azure.identity import DefaultAzureCredential
            client = CosmosClient(settings.azure_cosmos_endpoint, DefaultAzureCredential())

    db_name = database_name or settings.azure_cosmos_database
    container_name = container_name or settings.cosmos_search_container

    # Ensure the database exists
    database = client.create_database_if_not_exists(id=db_name)

    # Container definition with vector embedding policy
    # DiskANN is the recommended vector index type for Cosmos DB serverless
    container_properties: dict[str, Any] = {
        "id": container_name,
        "partitionKey": {
            "paths": ["/doc_type"],
            "kind": "Hash",
        },
        # Vector embedding policy — tells Cosmos DB which fields contain
        # vectors and how to index them
        "vectorEmbeddingPolicy": {
            "vectorEmbeddings": [
                {
                    "path": "/embedding",
                    "dataType": "float32",
                    "distanceFunction": "cosine",
                    "dimensions": EMBEDDING_DIMENSIONS,
                }
            ]
        },
        # Indexing policy — exclude the embedding from the default index
        # (it gets its own vector index) and add composite indexes for
        # common query patterns
        "indexingPolicy": {
            "indexingMode": "consistent",
            "automatic": True,
            "includedPaths": [{"path": "/*"}],
            "excludedPaths": [
                {"path": "/embedding/*"},  # vector field — indexed separately
                {"path": '/"_etag"/?'},
            ],
            "vectorIndexes": [
                {
                    "path": "/embedding",
                    "type": "diskANN",
                }
            ],
            "compositeIndexes": [
                # Support queries like "WHERE doc_type = 'rfp' ORDER BY _ts"
                [
                    {"path": "/doc_type", "order": "ascending"},
                    {"path": "/_ts", "order": "descending"},
                ]
            ],
        },
    }

    try:
        database.create_container_if_not_exists(
            id=container_name,
            partition_key=container_properties["partitionKey"],
            indexing_policy=container_properties["indexingPolicy"],
            vector_embedding_policy=container_properties["vectorEmbeddingPolicy"],
        )
        logger.info(
            "Cosmos search container '%s' ready (database='%s', dimensions=%d)",
            container_name,
            db_name,
            EMBEDDING_DIMENSIONS,
        )
    except Exception as exc:
        logger.error("Failed to create search container: %s", exc)
        raise
