"""Service factory — selects Azure or local backend by ``settings.backend``.

Every consumer (endpoints, MCP server, background pipeline) MUST obtain
its services through this module. Direct imports of ``CosmosService``,
``BlobStorageService``, etc. are reserved for the Azure backend
implementations themselves.

Selection rules
---------------
- ``settings.backend == "azure"`` → returns the current Azure SDK wrappers.
- ``settings.backend == "local"`` → returns the ChromaDB / SQLite /
  filesystem / Ollama / sentence-transformers implementations.

All factory functions return objects that duck-type as the Azure classes
so the agents and executors need no changes.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


# ── Backend guard ────────────────────────────────────────────────


def _is_local() -> bool:
    return settings.backend == "local"


# ── Record store (Cosmos / SQLite) ───────────────────────────────


@functools.lru_cache(maxsize=1)
def get_record_store() -> Any:
    """Document-record store — mirrors ``CosmosService`` interface."""
    if _is_local():
        from documind.services.local.sqlite_store import SQLiteRecordStore

        return SQLiteRecordStore()
    from documind.services.cosmos import CosmosService

    return CosmosService()


# ── Blob store (Azure Blob / filesystem) ─────────────────────────


@functools.lru_cache(maxsize=1)
def get_blob_store() -> Any:
    """Blob storage — mirrors ``BlobStorageService`` interface."""
    if _is_local():
        from documind.services.local.filesystem_blob import LocalBlobStorage

        return LocalBlobStorage()
    from documind.services.blob_storage import BlobStorageService

    return BlobStorageService()


# ── Search service (Cosmos vector / Chroma) ──────────────────────


@functools.lru_cache(maxsize=1)
def get_search_service() -> Any:
    """Vector + text search — mirrors ``VectorSearchService`` interface."""
    if _is_local():
        from documind.services.local.chroma_search import ChromaSearchService

        return ChromaSearchService()
    from documind.services.vector_search import VectorSearchService

    return VectorSearchService()


# ── Document extractor (Document Intelligence / local libs) ──────


@functools.lru_cache(maxsize=1)
def get_extractor() -> Any:
    """Document extractor — mirrors ``DocumentIntelligenceService`` interface."""
    if _is_local():
        from documind.services.local.local_extractor import LocalExtractor

        return LocalExtractor()
    from documind.services.document_intelligence import DocumentIntelligenceService

    return DocumentIntelligenceService()


# ── LLM caller (Azure OpenAI / Ollama / Gemini) ──────────────────


@functools.lru_cache(maxsize=1)
def get_llm_caller() -> Callable[[str], str]:
    """Return a ``Callable[[str], str]`` for the current backend."""
    if _is_local():
        if settings.local_llm_provider == "gemini":
            from documind.services.local.gemini_llm import make_gemini_caller

            return make_gemini_caller()
        from documind.services.local.ollama_llm import make_ollama_caller

        return make_ollama_caller()
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    if settings.azure_openai_key:
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version=settings.azure_openai_api_version,
        )
    else:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version=settings.azure_openai_api_version,
        )
    deployment = settings.azure_openai_deployment or settings.foundry_model_deployment

    def call_llm(prompt: str) -> str:
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
        )
        return response.choices[0].message.content or ""

    return call_llm


@functools.lru_cache(maxsize=1)
def get_llm_text_caller() -> Callable[[str], str]:
    """Return a plain-text LLM caller (no JSON mode) — used for RAG answers."""
    if _is_local():
        if settings.local_llm_provider == "gemini":
            from documind.services.local.gemini_llm import make_gemini_caller

            return make_gemini_caller(force_json=False)
        from documind.services.local.ollama_llm import make_ollama_caller

        return make_ollama_caller(force_json=False)
    # Azure OpenAI chat completions are plain-text by default; reuse the main caller.
    return get_llm_caller()


# ── Embedding function (Azure OpenAI / sentence-transformers) ────


@functools.lru_cache(maxsize=1)
def get_embedding_fn() -> Callable[[str], list[float]]:
    """Return a ``Callable[[str], list[float]]`` for the current backend."""
    if _is_local():
        from documind.services.local.ollama_llm import make_st_embedder

        return make_st_embedder()

    from documind.services.vector_search import _default_embedding_fn

    return _default_embedding_fn()
