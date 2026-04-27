"""Search & Retrieval Agent — workflow executor.

This is the final step in the document processing pipeline.  It
receives the extraction and analysis outputs and indexes the processed
document into Azure AI Search for querying.

It also exposes search methods that the API layer can call directly
(semantic search and faceted search are query-time operations, not
part of the ingestion pipeline).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from documind.agents.analysis.agent import AnalysisOutput
from documind.agents.search.tools.tools import (
    faceted_search,
    index_document,
    semantic_search,
)
from documind.core.models.base import AnalysisResult, ExtractionResult
from documind.doctypes.registry import DocTypeRegistry
from documind.services.search import SearchService

logger = logging.getLogger(__name__)


@dataclass
class SearchOutput:
    """Output produced by the Search Executor after indexing."""
    document_id: str
    index_result: dict[str, Any]


class SearchExecutor:
    """Search workflow step — index processed documents and handle queries.

    Pipeline mode (``run``):  indexes the document after analysis.
    Query mode (``search``, ``search_faceted``):  handles user queries.
    """

    def __init__(
        self,
        registry: DocTypeRegistry,
        search_service: SearchService,
    ) -> None:
        self._registry = registry
        self._search_service = search_service

    def run(self, inp: AnalysisOutput) -> SearchOutput:
        """Index the processed document into Azure AI Search.

        Called as the final pipeline step after analysis.
        """
        result = index_document(
            extraction=inp.extraction.extraction,
            analysis=inp.analysis,
            registry=self._registry,
            search_service=self._search_service,
        )

        logger.info(
            "Search indexing complete: id=%s succeeded=%s",
            inp.extraction.extraction.document_id,
            result["succeeded"],
        )
        return SearchOutput(
            document_id=inp.extraction.extraction.document_id,
            index_result=result,
        )

    def search(
        self,
        query: str,
        top: int = 5,
        filters: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a semantic search — used by the API layer."""
        return semantic_search(
            query=query,
            search_service=self._search_service,
            top=top,
            filters=filters,
        )

    def search_faceted(
        self,
        query: str,
        facets: list[str] | None = None,
        top: int = 10,
    ) -> dict[str, Any]:
        """Run a faceted search — used by the API layer."""
        facets = facets or ["doc_type"]
        return faceted_search(
            query=query,
            facets=facets,
            search_service=self._search_service,
            top=top,
        )
