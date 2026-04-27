"""RFP-specific Pydantic models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from documind.core.models.base import AnalysisResult, ExtractionResult


class EvaluationCriterion(BaseModel):
    criterion: str
    weight: Optional[float] = None
    description: str = ""


class RfpExtractionResult(ExtractionResult):
    """Extraction output for Request for Proposal documents."""

    doc_type: str = "rfp"
    issuing_organization: str = ""
    rfp_title: str = ""
    rfp_number: str = ""
    submission_deadline: str = ""
    scope_of_work: str = ""
    requirements: list[str] = Field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterion] = Field(default_factory=list)
    budget_range: str = ""
    contract_duration: str = ""
    point_of_contact: str = ""


class RfpAnalysisResult(AnalysisResult):
    """Analysis output for RFP documents."""

    doc_type: str = "rfp"
    executive_summary: str = ""
    key_requirements_count: int = 0
    mandatory_requirements: list[str] = Field(default_factory=list)
    optional_requirements: list[str] = Field(default_factory=list)
    compliance_gaps: list[str] = Field(default_factory=list)
