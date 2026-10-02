"""FastAPI dependency injection for DocuMind services.

Provides cached service instances via FastAPI's dependency system.
Services are created once (per-process) and reused across requests.

All accessors delegate to :mod:`documind.services.factory` so they
follow the ``settings.backend = "azure" | "local"`` switch.
"""

from __future__ import annotations

import functools

from documind.core.config.settings import settings
from documind.services import factory


@functools.lru_cache(maxsize=1)
def get_blob_service():
    """Singleton blob store (Azure or local)."""
    return factory.get_blob_store()


@functools.lru_cache(maxsize=1)
def get_cosmos_service():
    """Singleton record store (Azure Cosmos or SQLite)."""
    return factory.get_record_store()


@functools.lru_cache(maxsize=1)
def get_vector_search_service():
    """Singleton search service (Cosmos vector or ChromaDB)."""
    return factory.get_search_service()


def get_settings():
    """Return the application settings singleton."""
    return settings
