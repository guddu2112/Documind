"""API-layer request/response schemas (DTOs).

These wrap the internal ``core.models`` to decouple the public API
contract from internal data structures.  Changes to internal models
won't break API consumers as long as these DTOs are maintained.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from documind.core.models.base import (
    AnalysisResult,
    ExtractionResult,
    KeyValuePair,
    ExtractedTable,
    ProcessingStatus,
    RiskItem,
)


# ── Error ──────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Structured error returned by all error handlers."""

    error: str
    detail: str
    request_id: str = ""


# ── Documents ──────────────────────────────────────────────────────


class DocumentUploadResponse(BaseModel):
    """Returned after a successful document upload."""

    document_id: str
    filename: str
    doc_type: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    message: str = "Document accepted for processing."


class DocumentStatusResponse(BaseModel):
    """Current processing status of a document."""

    document_id: str
    doc_type: str
    status: ProcessingStatus
    filename: str = ""
    uploaded_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    stages_completed: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """Full analysis results for a processed document."""

    document_id: str
    doc_type: str
    status: ProcessingStatus
    extraction: Optional[ExtractionResult] = None
    analysis: Optional[AnalysisResult] = None


# ── Search ─────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    """Semantic search query."""

    query: str = Field(..., min_length=1, max_length=2000)
    doc_type: Optional[str] = Field(None, description="Filter by document type.")
    top: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchHit(BaseModel):
    """A single search result."""

    id: str
    content: str = ""
    score: float = 0.0
    doc_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Paginated search results."""

    query: str
    total: int = 0
    results: list[SearchHit] = Field(default_factory=list)
    offset: int = 0
    top: int = 10


# ── Ask (RAG) ──────────────────────────────────────────────────────


class AskRequest(BaseModel):
    """Natural-language question against the indexed corpus."""

    question: str = Field(..., min_length=1, max_length=2000)
    doc_type: Optional[str] = Field(None, description="Restrict retrieval to one document type.")
    top: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve for grounding.")


class AskCitation(BaseModel):
    """A document used to ground the answer."""

    id: str
    doc_type: str = ""
    score: float = 0.0
    preview: str = ""


class AskResponse(BaseModel):
    """RAG answer with citations."""

    question: str
    answer: str
    citations: list[AskCitation] = Field(default_factory=list)


# ── Health ─────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = "healthy"
    service: str = "documind-api"


class ReadinessCheck(BaseModel):
    """Status of a single dependency check."""

    name: str
    status: str  # "ok" or "error"
    detail: str = ""


class ReadinessResponse(BaseModel):
    """Readiness probe response with dependency checks."""

    status: str  # "ready" or "degraded"
    checks: list[ReadinessCheck] = Field(default_factory=list)


# ── Events ─────────────────────────────────────────────────────────


class PipelineEvent(BaseModel):
    """Real-time pipeline status event (sent via WS / SSE)."""

    document_id: str
    stage: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    detail: str = ""
