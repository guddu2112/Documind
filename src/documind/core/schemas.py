"""Structured output schemas for GPT-4o responses.

In Phase 1, the Analysis Agent parsed free-form JSON from GPT-4o using
``_safe_parse_json`` and hoped it matched our expected format.  This
worked in testing but is fragile in production — GPT-4o occasionally
returns extra keys, missing fields, or malformed JSON.

Phase 2 introduces **structured output** using JSON Schema definitions
that are passed to GPT-4o's ``response_format`` parameter.  This
guarantees the LLM response conforms to the schema — no more parsing
failures.

Each doc type's analysis tasks have a corresponding JSON Schema here.
The schemas are designed to match the output our downstream code
expects (AnalysisResult, RiskItem, etc.).

Usage::

    from documind.core.schemas import get_response_schema

    schema = get_response_schema("rfp", "summarize")
    # Pass schema to GPT-4o's response_format parameter

See Also:
    - OpenAI structured output docs: response_format={"type": "json_schema", ...}
    - Our AnalysisResult model: documind.core.models.base.AnalysisResult
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Risk item schema (shared across all doc types) ─────────────────

_RISK_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Short title describing the risk.",
        },
        "description": {
            "type": "string",
            "description": "Detailed explanation of the risk.",
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
            "description": "Risk severity level.",
        },
        "recommendation": {
            "type": "string",
            "description": "Suggested mitigation or action.",
        },
    },
    "required": ["title", "description", "severity"],
    "additionalProperties": False,
}

# ── RFP Summary Schema ────────────────────────────────────────────

_RFP_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "rfp_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "executive_summary": {
                    "type": "string",
                    "description": "High-level executive summary of the RFP.",
                },
                "mandatory_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of mandatory requirements from the RFP.",
                },
                "optional_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of optional / nice-to-have requirements.",
                },
                "evaluation_criteria": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "criterion": {"type": "string"},
                            "weight": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["criterion", "weight", "description"],
                        "additionalProperties": False,
                    },
                    "description": "Evaluation criteria with weights.",
                },
                "key_dates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "event": {"type": "string"},
                            "date": {"type": "string"},
                        },
                        "required": ["event", "date"],
                        "additionalProperties": False,
                    },
                    "description": "Important dates and deadlines.",
                },
                "budget_range": {
                    "type": "string",
                    "description": "Budget range or ceiling if disclosed.",
                },
                "risks": {
                    "type": "array",
                    "items": _RISK_ITEM_SCHEMA,
                    "description": "Identified risks and concerns.",
                },
            },
            "required": [
                "executive_summary",
                "mandatory_requirements",
                "optional_requirements",
                "evaluation_criteria",
                "key_dates",
                "budget_range",
                "risks",
            ],
            "additionalProperties": False,
        },
    },
}

# ── Contract Clauses Schema ────────────────────────────────────────

_CONTRACT_CLAUSES_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "contract_clauses",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "executive_summary": {
                    "type": "string",
                    "description": "Brief summary of the contract.",
                },
                "parties": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names of all parties to the contract.",
                },
                "clauses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clause_number": {"type": "string"},
                            "title": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": [
                                    "liability",
                                    "indemnification",
                                    "termination",
                                    "confidentiality",
                                    "intellectual_property",
                                    "payment",
                                    "performance",
                                    "dispute_resolution",
                                    "other",
                                ],
                            },
                            "summary": {"type": "string"},
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                            },
                            "negotiation_notes": {"type": "string"},
                        },
                        "required": [
                            "clause_number",
                            "title",
                            "category",
                            "summary",
                            "risk_level",
                            "negotiation_notes",
                        ],
                        "additionalProperties": False,
                    },
                    "description": "Extracted clauses with risk assessment.",
                },
                "risks": {
                    "type": "array",
                    "items": _RISK_ITEM_SCHEMA,
                    "description": "Overall contract risks.",
                },
            },
            "required": [
                "executive_summary",
                "parties",
                "clauses",
                "risks",
            ],
            "additionalProperties": False,
        },
    },
}

# ── Spec Compliance Schema ─────────────────────────────────────────

_SPEC_COMPLIANCE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "spec_compliance",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "executive_summary": {
                    "type": "string",
                    "description": "Summary of the specification's quality.",
                },
                "completeness_score": {
                    "type": "number",
                    "description": "Score 0-100 for requirements completeness.",
                },
                "clarity_score": {
                    "type": "number",
                    "description": "Score 0-100 for requirements clarity.",
                },
                "standards_alignment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "standard": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["compliant", "partial", "non_compliant", "not_assessed"],
                            },
                            "notes": {"type": "string"},
                        },
                        "required": ["standard", "status", "notes"],
                        "additionalProperties": False,
                    },
                    "description": "Compliance with referenced standards.",
                },
                "gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Missing requirements or coverage gaps.",
                },
                "ambiguities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ambiguous or unclear requirements.",
                },
                "risks": {
                    "type": "array",
                    "items": _RISK_ITEM_SCHEMA,
                    "description": "Risks identified in the specification.",
                },
            },
            "required": [
                "executive_summary",
                "completeness_score",
                "clarity_score",
                "standards_alignment",
                "gaps",
                "ambiguities",
                "risks",
            ],
            "additionalProperties": False,
        },
    },
}

# ── Schema registry ────────────────────────────────────────────────
# Maps (doc_type, task_name) → JSON Schema for GPT-4o response_format.

_SCHEMA_REGISTRY: dict[tuple[str, str], dict[str, Any]] = {
    ("rfp", "summarize"): _RFP_SUMMARY_SCHEMA,
    ("contract", "extract_clauses"): _CONTRACT_CLAUSES_SCHEMA,
    ("spec", "compliance_check"): _SPEC_COMPLIANCE_SCHEMA,
}


def get_response_schema(
    doc_type: str,
    task_name: str,
) -> dict[str, Any] | None:
    """Look up the structured output schema for a (doc_type, task) pair.

    Returns the JSON Schema dict suitable for GPT-4o's response_format
    parameter, or None if no schema is registered (falls back to
    unstructured output).

    Args:
        doc_type:   Document type identifier (e.g. "rfp", "contract").
        task_name:  Analysis task name (e.g. "summarize", "extract_clauses").

    Returns:
        JSON Schema dict or None.
    """
    schema = _SCHEMA_REGISTRY.get((doc_type, task_name))
    if schema:
        logger.debug("Found schema for (%s, %s)", doc_type, task_name)
    else:
        logger.debug("No schema for (%s, %s) — using unstructured output", doc_type, task_name)
    return schema


def list_registered_schemas() -> list[tuple[str, str]]:
    """Return all registered (doc_type, task_name) pairs.

    Useful for testing and documentation.
    """
    return list(_SCHEMA_REGISTRY.keys())
