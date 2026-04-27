"""Search endpoints — semantic and faceted search.

Routes:
    POST /search — Run a semantic search query against indexed documents.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from documind.api.schemas import SearchHit, SearchRequest, SearchResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic search across processed documents",
)
async def search_documents(body: SearchRequest):
    """Run a semantic vector search against the Cosmos DB search index.

    Supports optional filtering by ``doc_type`` and pagination via
    ``top`` / ``offset``.
    """
    from documind.services.vector_search import VectorSearchService

    try:
        svc = VectorSearchService()
        raw_results = svc.semantic_search(
            query=body.query,
            top=body.top,
            filters=f"c.doc_type = '{body.doc_type}'" if body.doc_type else None,
        )
    except Exception as exc:
        logger.exception("Search failed for query: %s", body.query)
        raise HTTPException(status_code=500, detail="Search failed.") from exc

    hits = [
        SearchHit(
            id=r.get("id", ""),
            content=r.get("content", ""),
            score=r.get("score", 0.0),
            doc_type=r.get("doc_type", ""),
            metadata={k: v for k, v in r.items() if k not in ("id", "content", "score", "doc_type")},
        )
        for r in raw_results
    ]

    return SearchResponse(
        query=body.query,
        total=len(hits),
        results=hits[body.offset : body.offset + body.top],
        offset=body.offset,
        top=body.top,
    )
