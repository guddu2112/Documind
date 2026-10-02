"""Base Pydantic models shared across all document types.

Every doc-type-specific model inherits from these so the pipeline
can handle any document type through a uniform interface.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


# ------------------------------------------------------------------
# Shared value objects
# ------------------------------------------------------------------


class KeyValuePair(BaseModel):
    """A single key-value pair extracted from a document."""

    key: str
    value: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    page: Optional[int] = None


class TableCell(BaseModel):
    row: int
    column: int
    content: str
    is_header: bool = False


class ExtractedTable(BaseModel):
    """A table extracted from a document."""

    table_id: int = 0
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    page: Optional[int] = None


class RiskItem(BaseModel):
    """A risk identified during analysis."""

    title: str
    description: str
    severity: RiskSeverity = RiskSeverity.MEDIUM
    clause_reference: Optional[str] = None
    recommendation: str = ""


# ------------------------------------------------------------------
# Base results
# ------------------------------------------------------------------


class ExtractionResult(BaseModel):
    """Base model for all extraction outputs.

    Each doc-type module extends this with type-specific fields while
    the pipeline code only depends on this base interface.
    """

    document_id: str
    doc_type: str
    source_filename: str
    page_count: int = 0
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    key_value_pairs: list[KeyValuePair] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    raw_text: str = ""
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Base model for all analysis outputs."""

    document_id: str
    doc_type: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""
    risks: list[RiskItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    """Top-level record persisted in Cosmos DB for pipeline state."""

    document_id: str
    doc_type: str
    source_filename: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    extraction: Optional[ExtractionResult] = None
    analysis: Optional[AnalysisResult] = None
    blob_url: str = ""
    error_message: Optional[str] = None
    stages_completed: list[str] = Field(default_factory=list)
