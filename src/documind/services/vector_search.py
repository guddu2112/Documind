"""Cosmos DB vector search service — replaces Azure AI Search.

This module provides document indexing and vector/full-text search using
Azure Cosmos DB's built-in vector search (DiskANN) instead of the
separate (and expensive) Azure AI Search service.

Why Cosmos DB instead of AI Search?
    - Serverless pricing: $0 fixed cost, pay-per-RU only.
    - Vector search via DiskANN: competitive recall with HNSW.
    - Full-text search: keyword queries without a separate index.
    - Single database: documents, metadata, and vectors in one place.
    - Already provisioned in our Terraform for pipeline state tracking.

Architecture:
    - Container "documents": stores pipeline state (existing).
    - Container "search_index": stores search documents with embeddings.

The ``VectorSearchService`` is a drop-in replacement for the old
``SearchService`` — it implements the same public interface so the
SearchExecutor and tools don't need changes.

Usage::

    service = VectorSearchService()
    service.index_document({"id": "doc-1", "content": "...", "embedding": [...]})
    results = service.vector_search("what is the deadline?", top=5)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)

# Cosmos DB vector search container name
_SEARCH_CONTAINER = "search_index"

# Embedding dimensions for text-embedding-3-small
EMBEDDING_DIMENSIONS = 1536


def _default_cosmos_client():
    """Build a CosmosClient from settings.

    Reuses the same Cosmos DB account that stores pipeline state — no
    additional Azure resource needed.
    """
    from azure.cosmos import CosmosClient

    if settings.azure_cosmos_key:
        return CosmosClient(settings.azure_cosmos_endpoint, settings.azure_cosmos_key)
    from azure.identity import DefaultAzureCredential

    return CosmosClient(settings.azure_cosmos_endpoint, DefaultAzureCredential())


class VectorSearchService:
    """Search service backed by Cosmos DB with vector search (DiskANN).

    Implements the same public interface as the old AI Search-based
    SearchService so the SearchExecutor works without changes.

    The service uses two Cosmos features:
        1. **Vector search** — for semantic similarity using embeddings.
        2. **SQL queries** — for filtered and faceted searches.
    """

    def __init__(
        self,
        client=None,
        database_name: str | None = None,
        container_name: str | None = None,
        embedding_fn=None,
    ) -> None:
        """Initialise the vector search service.

        Args:
            client:         Optional CosmosClient (injected for testing).
            database_name:  Cosmos DB database name (defaults to settings).
            container_name: Container for search documents (defaults to "search_index").
            embedding_fn:   Callable that converts text → list[float].
                            If None, a default Azure OpenAI embedder is used.
        """
        self._client = client or _default_cosmos_client()
        self._database_name = database_name or settings.azure_cosmos_database
        self._container_name = container_name or _SEARCH_CONTAINER
        self._embedding_fn = embedding_fn or _default_embedding_fn()

    @property
    def _container(self):
        """Lazy reference to the search index container."""
        db = self._client.get_database_client(self._database_name)
        return db.get_container_client(self._container_name)

    # ── Indexing ───────────────────────────────────────────────────

    def index_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Index (upsert) a document into the Cosmos search container.

        The document must have an ``id`` field.  If ``content`` is present
        and ``embedding`` is not, we auto-generate the embedding.

        Returns a result dict with ``succeeded`` and ``key`` fields,
        matching the old SearchService interface.
        """
        doc_id = document.get("id", "")

        # Auto-generate embedding from content if not provided
        if "embedding" not in document and "content" in document:
            content_text = document["content"]
            # Also include summary for richer semantic representation
            if "summary" in document:
                content_text = f"{document['summary']}\n\n{content_text}"
            document["embedding"] = self._embedding_fn(content_text)

        # Upsert — creates if new, replaces if exists
        try:
            self._container.upsert_item(body=document)
            logger.info("Indexed document id=%s", doc_id)
            return {"succeeded": True, "key": doc_id}
        except Exception as exc:
            logger.error("Failed to index document id=%s: %s", doc_id, exc)
            return {"succeeded": False, "key": doc_id, "error": str(exc)}

    # ── Vector search ──────────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top: int = 5,
        filters: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a vector similarity search using query embeddings.

        Generates an embedding for the query text, then finds the most
        similar documents in the Cosmos container using the DiskANN
        vector index.

        The ``filters`` parameter accepts a SQL WHERE clause fragment
        (e.g. ``"c.doc_type = 'rfp'"``).
        """
        # Generate query embedding
        query_embedding = self._embedding_fn(query)

        # Build the Cosmos DB vector search query
        # Uses the VectorDistance() function with cosine similarity
        where_clause = f"AND {filters}" if filters else ""
        sql = f"""
            SELECT TOP @top
                c.id,
                c.doc_type,
                c.source_filename,
                c.content,
                c.summary,
                c.risks,
                VectorDistance(c.embedding, @queryEmbedding) AS score
            FROM c
            WHERE 1=1 {where_clause}
            ORDER BY VectorDistance(c.embedding, @queryEmbedding)
        """
        parameters = [
            {"name": "@top", "value": top},
            {"name": "@queryEmbedding", "value": query_embedding},
        ]

        results = list(
            self._container.query_items(
                query=sql,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        logger.info("Vector search '%s' → %d results", query, len(results))
        return results

    # ── Faceted search ─────────────────────────────────────────────

    def faceted_search(
        self,
        query: str,
        facets: list[str],
        top: int = 10,
    ) -> dict[str, Any]:
        """Search with faceted counts for drill-down filtering.

        Since Cosmos DB doesn't have built-in facets like AI Search,
        we run two queries:
            1. Main results query with keyword matching.
            2. Aggregation queries for each facet field.

        Returns ``{"results": [...], "facets": {"field": [{"value": ..., "count": ...}]}}``.
        """
        # Main results — simple text search using CONTAINS
        results_sql = """
            SELECT TOP @top c.id, c.doc_type, c.source_filename,
                   c.content, c.summary, c.risks
            FROM c
            WHERE CONTAINS(LOWER(c.content), LOWER(@query))
               OR CONTAINS(LOWER(c.summary), LOWER(@query))
        """
        results = list(
            self._container.query_items(
                query=results_sql,
                parameters=[
                    {"name": "@top", "value": top},
                    {"name": "@query", "value": query},
                ],
                enable_cross_partition_query=True,
            )
        )

        # Facet counts — one aggregation per facet field
        facet_results: dict[str, list[dict[str, Any]]] = {}
        for facet_field in facets:
            facet_sql = f"""
                SELECT c.{facet_field} AS value, COUNT(1) AS count
                FROM c
                GROUP BY c.{facet_field}
            """
            try:
                facet_data = list(
                    self._container.query_items(
                        query=facet_sql,
                        enable_cross_partition_query=True,
                    )
                )
                facet_results[facet_field] = [
                    {"value": f["value"], "count": f["count"]}
                    for f in facet_data
                    if f.get("value") is not None
                ]
            except Exception as exc:
                logger.warning("Facet query for '%s' failed: %s", facet_field, exc)
                facet_results[facet_field] = []

        logger.info(
            "Faceted search '%s' → %d results, %d facet fields",
            query, len(results), len(facet_results),
        )
        return {"results": results, "facets": facet_results}


# ── Default embedding function ─────────────────────────────────────


def _default_embedding_fn():
    """Create an embedding function using Azure OpenAI text-embedding-3-small.

    Returns a callable that converts text → list[float].

    This is lazily initialised so the import doesn't fail in test
    environments where Azure OpenAI isn't available.
    """

    def embed(text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses the Azure OpenAI embedding model configured in settings.
        Truncates input to 8191 tokens (model limit).
        """
        from openai import AzureOpenAI
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-02-01",
        )
        response = client.embeddings.create(
            input=text[:32000],  # rough truncation to stay under token limit
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    return embed
