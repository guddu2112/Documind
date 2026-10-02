"""ChromaDB-backed search service — offline replacement for
``VectorSearchService``.

Uses an embedded (persistent) ChromaDB client so no separate server is
needed. Embeddings come from ``ollama_llm.make_st_embedder()`` (sentence-
transformers) unless a caller injects their own.

Public interface mirrors ``VectorSearchService`` exactly:
    - index_document(document: dict) -> dict
    - semantic_search(query: str, top: int, filters: str | None) -> list[dict]
    - faceted_search(query: str, facets: list[str], top: int) -> dict
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


# ── Cosmos-style "filters" → Chroma `where` translation ──────────

# Match: c.<field> = '<value>'  OR  c.<field>='<value>'
_FILTER_RE = re.compile(r"c\.(?P<field>\w+)\s*=\s*'(?P<value>[^']*)'")


def _translate_filters(filters: Optional[str]) -> Optional[dict[str, Any]]:
    """Translate the small SQL fragment used by the current codebase into
    a Chroma ``where`` clause. Multiple ``AND``-joined equalities are
    supported; anything unrecognised is logged and ignored.
    """
    if not filters:
        return None
    matches = _FILTER_RE.findall(filters)
    if not matches:
        logger.warning("Chroma: unsupported filter fragment ignored: %r", filters)
        return None
    equalities = {field: value for field, value in matches}
    if len(equalities) == 1:
        field, value = next(iter(equalities.items()))
        return {field: value}
    return {"$and": [{f: v} for f, v in equalities.items()]}


# ── Metadata sanitisation ────────────────────────────────────────

# Chroma metadata must be scalar (str/int/float/bool). Collapse lists/dicts
# to a JSON string and drop the embedding.
def _flatten_metadata(document: dict[str, Any]) -> dict[str, Any]:
    import json

    meta: dict[str, Any] = {}
    for key, value in document.items():
        if key in ("id", "embedding", "content"):
            continue
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            meta[key] = value
        else:
            try:
                meta[key] = json.dumps(value, default=str)
            except Exception:
                meta[key] = str(value)
    return meta


# ── Service ──────────────────────────────────────────────────────


class ChromaSearchService:
    """Search service backed by a persistent embedded ChromaDB."""

    def __init__(
        self,
        client: Any = None,
        collection_name: str | None = None,
        persist_path: str | None = None,
        embedding_fn: Optional[Callable[[str], list[float]]] = None,
    ) -> None:
        self._collection_name = collection_name or settings.chroma_collection
        self._persist_path = str(Path(persist_path or settings.chroma_path).expanduser().resolve())
        Path(self._persist_path).mkdir(parents=True, exist_ok=True)

        if client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            client = chromadb.PersistentClient(
                path=self._persist_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._client = client
        self._collection = client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        if embedding_fn is None:
            from documind.services.local.ollama_llm import make_st_embedder

            embedding_fn = make_st_embedder()
        self._embedding_fn = embedding_fn

        logger.info(
            "ChromaSearchService ready: path=%s collection=%s",
            self._persist_path,
            self._collection_name,
        )

    # ── Indexing ───────────────────────────────────────────────

    def index_document(self, document: dict[str, Any]) -> dict[str, Any]:
        doc_id = document.get("id", "")
        if not doc_id:
            return {"succeeded": False, "key": "", "error": "missing id"}

        content_text = document.get("content", "") or ""
        if "summary" in document and document["summary"]:
            content_text = f"{document['summary']}\n\n{content_text}"

        embedding = document.get("embedding")
        if embedding is None:
            embedding = self._embedding_fn(content_text or doc_id)

        try:
            self._collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content_text],
                metadatas=[_flatten_metadata(document)],
            )
            logger.info("Indexed document id=%s", doc_id)
            return {"succeeded": True, "key": doc_id}
        except Exception as exc:
            logger.error("Failed to index document id=%s: %s", doc_id, exc)
            return {"succeeded": False, "key": doc_id, "error": str(exc)}

    # ── Semantic search ────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top: int = 5,
        filters: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        query_embedding = self._embedding_fn(query)
        where = _translate_filters(filters)

        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=max(top, 1),
            where=where,
        )

        hits: list[dict[str, Any]] = []
        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            distance = distances[i] if i < len(distances) else 0.0
            hit: dict[str, Any] = {
                "id": doc_id,
                "content": docs[i] if i < len(docs) else "",
                "score": 1.0 - float(distance),
            }
            if isinstance(meta, dict):
                hit.update(meta)
            hits.append(hit)

        logger.info("Vector search '%s' → %d results", query, len(hits))
        return hits

    # ── Faceted search ─────────────────────────────────────────

    def faceted_search(
        self,
        query: str,
        facets: list[str],
        top: int = 10,
    ) -> dict[str, Any]:
        results = self.semantic_search(query, top=top)

        facet_counts: dict[str, list[dict[str, Any]]] = {}
        if not facets:
            return {"results": results, "facets": facet_counts}

        # Aggregate over the full collection so counts don't depend on
        # the current query result set.
        all_docs = self._collection.get(include=["metadatas"])
        metas = all_docs.get("metadatas") or []
        for field in facets:
            counts: dict[str, int] = {}
            for meta in metas:
                if not isinstance(meta, dict):
                    continue
                value = meta.get(field)
                if value is None:
                    continue
                counts[str(value)] = counts.get(str(value), 0) + 1
            facet_counts[field] = [
                {"value": v, "count": c} for v, c in sorted(counts.items())
            ]

        return {"results": results, "facets": facet_counts}
