"""FastAPI dependency injection for DocuMind services.

Provides cached service instances via FastAPI's dependency system.
Services are created once (per-process) and reused across requests.
"""

from __future__ import annotations

import functools

from documind.core.config.settings import settings
from documind.services.blob_storage import BlobStorageService
from documind.services.cosmos import CosmosService
from documind.services.vector_search import VectorSearchService


@functools.lru_cache(maxsize=1)
def get_blob_service() -> BlobStorageService:
    """Singleton BlobStorageService."""
    return BlobStorageService()


@functools.lru_cache(maxsize=1)
def get_cosmos_service() -> CosmosService:
    """Singleton CosmosService."""
    return CosmosService()


@functools.lru_cache(maxsize=1)
def get_vector_search_service() -> VectorSearchService:
    """Singleton VectorSearchService."""
    return VectorSearchService()


def get_settings():
    """Return the application settings singleton."""
    return settings
