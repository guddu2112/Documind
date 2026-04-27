"""Contract-specific Pydantic models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from documind.core.models.base import AnalysisResult, ExtractionResult, RiskSeverity


class ContractClause(BaseModel):
    clause_number: str = ""
    title: str
    content: str
    category: str = ""
    risk_level: RiskSeverity = RiskSeverity.LOW


class Obligation(BaseModel):
    party: str
    obligation: str
    deadline: str = ""


class ContractExtractionResult(ExtractionResult):
    """Extraction output for Contract / Agreement documents."""

    doc_type: str = "contract"
    contract_title: str = ""
    parties: list[str] = Field(default_factory=list)
    effective_date: str = ""
    expiration_date: str = ""
    contract_value: str = ""
    payment_terms: str = ""
    key_clauses: list[ContractClause] = Field(default_factory=list)
    termination_conditions: list[str] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    governing_law: str = ""


class ContractAnalysisResult(AnalysisResult):
    """Analysis output for contract documents."""

    doc_type: str = "contract"
    clause_count: int = 0
    high_risk_clauses: list[ContractClause] = Field(default_factory=list)
    missing_clauses: list[str] = Field(default_factory=list)
    negotiation_points: list[str] = Field(default_factory=list)
