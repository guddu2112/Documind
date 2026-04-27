# DocuMind Services - Azure SDK wrappers
#
# Each service class wraps one Azure SDK and can be injected with a mock
# client for testing (pass client=... to the constructor).

from documind.services.blob_storage import BlobStorageService
from documind.services.chunker import DocumentChunker, Chunk, merge_chunk_results
from documind.services.cosmos import CosmosService
from documind.services.document_intelligence import DocumentIntelligenceService
from documind.services.prompt_loader import PromptLoader
from documind.services.search import SearchService
from documind.services.vector_search import VectorSearchService

__all__ = [
    "BlobStorageService",
    "Chunk",
    "CosmosService",
    "DocumentChunker",
    "DocumentIntelligenceService",
    "PromptLoader",
    "SearchService",
    "VectorSearchService",
    "merge_chunk_results",
]
