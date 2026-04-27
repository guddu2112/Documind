"""Azure AI Search service wrapper.

Provides indexing (upload) and search (semantic + faceted) operations
against the DocuMind search index.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


def _default_search_client():
    """Build a SearchClient for querying."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    if settings.azure_search_key:
        credential = AzureKeyCredential(settings.azure_search_key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    return SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=credential,
    )


def _default_index_client():
    """Build a SearchIndexClient for index management."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    if settings.azure_search_key:
        credential = AzureKeyCredential(settings.azure_search_key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    return SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )


class SearchService:
    """Wraps Azure AI Search for indexing and querying documents."""

    def __init__(self, search_client=None, index_client=None) -> None:
        self._search_client = search_client or _default_search_client()
        self._index_client = index_client or _default_index_client()

    def index_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Upload a single document to the search index.

        *document* must contain an ``id`` field (the index key).
        Returns the indexing result for this document.
        """
        # merge_or_upload creates the doc if new, updates if existing
        result = self._search_client.merge_or_upload_documents([document])
        succeeded = [r for r in result if r.succeeded]
        logger.info(
            "Indexed document id=%s — succeeded=%d",
            document.get("id", "?"),
            len(succeeded),
        )
        return {"succeeded": len(succeeded) > 0, "key": document.get("id")}

    def semantic_search(
        self,
        query: str,
        top: int = 5,
        filters: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a semantic search query.

        Uses Azure AI Search's semantic ranker for natural-language queries.
        Returns a list of result dicts with ``score`` and document fields.
        """
        results = self._search_client.search(
            search_text=query,
            query_type="semantic",
            semantic_configuration_name="default",
            top=top,
            filter=filters,
        )
        hits: list[dict[str, Any]] = []
        for r in results:
            hit = dict(r)
            hit["score"] = getattr(r, "@search.score", 0.0)
            hits.append(hit)
        logger.info("Semantic search for '%s' returned %d hits", query, len(hits))
        return hits

    def faceted_search(
        self,
        query: str,
        facets: list[str],
        top: int = 10,
    ) -> dict[str, Any]:
        """Search with faceted results for drill-down filtering.

        Returns ``{"results": [...], "facets": {"field": [{"value": ..., "count": ...}]}}``.
        """
        results = self._search_client.search(
            search_text=query,
            facets=facets,
            top=top,
        )
        hits = [dict(r) for r in results]
        # Facet counts come from the results object
        facet_results = {}
        if hasattr(results, "get_facets"):
            raw_facets = results.get_facets() or {}
            for field, values in raw_facets.items():
                facet_results[field] = [
                    {"value": v.get("value"), "count": v.get("count")}
                    for v in values
                ]
        return {"results": hits, "facets": facet_results}
