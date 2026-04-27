"""Technical Specification-specific Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from documind.core.models.base import AnalysisResult, ExtractionResult


class Requirement(BaseModel):
    req_id: str = ""
    description: str
    priority: str = ""  # e.g. "must", "should", "may"
    category: str = ""  # functional / non-functional


class AcceptanceCriterion(BaseModel):
    req_id: str = ""
    criterion: str
    verification_method: str = ""


class SpecExtractionResult(ExtractionResult):
    """Extraction output for Technical Specification documents."""

    doc_type: str = "spec"
    document_title: str = ""
    document_version: str = ""
    author: str = ""
    functional_requirements: list[Requirement] = Field(default_factory=list)
    non_functional_requirements: list[Requirement] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    standards_references: list[str] = Field(default_factory=list)
    assumptions_constraints: list[str] = Field(default_factory=list)
    glossary: dict[str, str] = Field(default_factory=dict)


class SpecAnalysisResult(AnalysisResult):
    """Analysis output for spec documents."""

    doc_type: str = "spec"
    total_requirements: int = 0
    ambiguous_requirements: list[str] = Field(default_factory=list)
    missing_acceptance_criteria: list[str] = Field(default_factory=list)
    standards_compliance: dict[str, bool] = Field(default_factory=dict)
    completeness_score: float = Field(0.0, ge=0.0, le=1.0)
