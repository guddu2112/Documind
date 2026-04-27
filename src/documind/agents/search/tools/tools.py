"""Search & Retrieval Agent function tools.

Three tools as specified in the plan:

1. **index_document**  — upload extraction + analysis results to Azure AI Search
2. **semantic_search** — natural-language search with semantic ranking
3. **faceted_search**  — structured search with facet counts for filtering

The ``SearchService`` dependency is injected for testability.
"""

from __future__ import annotations

import logging
from typing import Any

from documind.core.models.base import AnalysisResult, ExtractionResult
from documind.doctypes.registry import DocTypeRegistry
from documind.services.search import SearchService

logger = logging.getLogger(__name__)


def index_document(
    extraction: ExtractionResult,
    analysis: AnalysisResult,
    registry: DocTypeRegistry,
    search_service: SearchService,
) -> dict[str, Any]:
    """Index a processed document into Azure AI Search.

    Builds a search document by mapping extraction and analysis fields
    according to the doc-type config's ``search_field_mappings``.  This
    ensures each doc type can define its own index schema without
    changing this function.
    """
    doc_config = registry.get(extraction.doc_type)

    # Start with common fields every document has
    search_doc: dict[str, Any] = {
        "id": extraction.document_id,
        "doc_type": extraction.doc_type,
        "source_filename": extraction.source_filename,
        "content": extraction.raw_text,
        "summary": analysis.summary,
        "page_count": extraction.page_count,
    }

    # Apply doc-type-specific field mappings
    # The mappings connect extraction/analysis output fields to index fields
    combined_data = {
        **extraction.model_dump(),
        **analysis.model_dump(),
    }
    for mapping in doc_config.search_field_mappings:
        value = combined_data.get(mapping.source_field)
        if value is not None:
            # Convert lists to comma-separated strings for searchability
            if isinstance(value, list):
                search_doc[mapping.index_field] = ", ".join(str(v) for v in value)
            else:
                search_doc[mapping.index_field] = value

    # Add risk summary as a searchable field
    if analysis.risks:
        search_doc["risks"] = "; ".join(
            f"{r.title} ({r.severity.value})" for r in analysis.risks
        )

    result = search_service.index_document(search_doc)
    logger.info("Indexed document %s → succeeded=%s", extraction.document_id, result["succeeded"])
    return result


def semantic_search(
    query: str,
    search_service: SearchService,
    top: int = 5,
    filters: str | None = None,
) -> list[dict[str, Any]]:
    """Run a natural-language semantic search across indexed documents.

    Uses Azure AI Search's semantic ranker to find the most relevant
    documents based on meaning, not just keyword matching.
    """
    results = search_service.semantic_search(
        query=query,
        top=top,
        filters=filters,
    )
    logger.info("Semantic search '%s' → %d results", query, len(results))
    return results


def faceted_search(
    query: str,
    facets: list[str],
    search_service: SearchService,
    top: int = 10,
) -> dict[str, Any]:
    """Search with faceted results for drill-down filtering.

    Facets let the UI show counts per category (e.g. "3 RFPs, 5 contracts")
    so users can narrow results without re-querying.
    """
    result = search_service.faceted_search(
        query=query,
        facets=facets,
        top=top,
    )
    logger.info(
        "Faceted search '%s' → %d results, %d facet fields",
        query,
        len(result["results"]),
        len(result["facets"]),
    )
    return result
