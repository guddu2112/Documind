"""Pydantic schema that defines a document-type configuration.

Each YAML file in ``doctypes/types/`` is validated against this schema at
startup.  The schema is intentionally flat and declarative so that new doc
types can be onboarded without writing Python code.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SupportedFormat(str, Enum):
    """File formats the pipeline can ingest."""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PNG = "png"
    JPG = "jpg"
    TIFF = "tiff"


class ExtractionFieldConfig(BaseModel):
    """Declares a single field the Extraction Agent should produce."""

    name: str = Field(..., description="Machine-readable field name (snake_case).")
    label: str = Field(..., description="Human-readable label shown in UI.")
    field_type: str = Field(
        "text",
        description="Logical type: text, date, currency, list, table, boolean.",
    )
    required: bool = Field(True, description="Whether the field must be extracted.")
    description: str = Field("", description="Hint given to the LLM for extraction.")


class AnalysisTaskConfig(BaseModel):
    """Declares an analysis task the Analysis Agent should run for this doc type."""

    name: str = Field(..., description="Task identifier (e.g. 'summarize', 'extract_clauses').")
    prompt_template: str = Field(
        ...,
        description="Filename of the Jinja2 prompt template (relative to prompts dir).",
    )
    description: str = Field("", description="Human-readable description of what the task does.")


class SearchFieldMapping(BaseModel):
    """Maps an extraction/analysis field to an Azure AI Search index field."""

    source_field: str = Field(..., description="Field name from extraction or analysis output.")
    index_field: str = Field(..., description="Target field name in the search index.")
    searchable: bool = Field(True)
    filterable: bool = Field(False)
    facetable: bool = Field(False)


class DocumentTypeConfig(BaseModel):
    """Top-level configuration for a pluggable document type.

    One YAML file per document type, validated against this schema.
    """

    name: str = Field(..., description="Unique doc-type identifier (e.g. 'rfp').")
    display_name: str = Field(..., description="Human-friendly name (e.g. 'Request for Proposal').")
    description: str = Field("", description="What this document type represents.")
    supported_formats: list[SupportedFormat] = Field(
        default_factory=lambda: [SupportedFormat.PDF, SupportedFormat.DOCX],
        description="File formats accepted for this doc type.",
    )
    extraction_fields: list[ExtractionFieldConfig] = Field(
        default_factory=list,
        description="Fields the Extraction Agent should produce.",
    )
    analysis_tasks: list[AnalysisTaskConfig] = Field(
        default_factory=list,
        description="Analysis tasks the Analysis Agent should run.",
    )
    search_field_mappings: list[SearchFieldMapping] = Field(
        default_factory=list,
        description="Mappings from extraction/analysis output to search index fields.",
    )
    doc_intelligence_model: str = Field(
        "prebuilt-layout",
        description="Azure Document Intelligence model ID to use.",
    )
    enabled: bool = Field(True, description="Set to false to disable a doc type without removing it.")
    version: str = Field("1.0", description="Config version for migration tracking.")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata.",
    )
