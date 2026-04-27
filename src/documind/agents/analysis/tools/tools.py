"""Analysis Agent function tools.

These functions use GPT-4o (via an LLM caller) to analyze extracted
document text.  Each tool:

1. Loads the appropriate Jinja2 prompt template for the doc type.
2. Renders the prompt with the document text.
3. Calls the LLM and returns the structured response.

The ``llm_caller`` is a callable ``(prompt: str) -> str`` so we can
inject a real LLM client or a mock for testing.

Four tools as specified in the plan:
- **summarize_document** — executive summary of any doc type
- **extract_clauses**    — clause extraction (primarily for contracts)
- **identify_risks**     — risk identification for any doc type
- **check_compliance**   — compliance check (primarily for specs)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from documind.agents.analysis.task_registry import register_task
from documind.core.models.base import AnalysisResult, RiskItem, RiskSeverity
from documind.doctypes.schema import AnalysisTaskConfig
from documind.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

# Type alias for the LLM calling function
# Accepts a system prompt string and returns the LLM's response string
LLMCaller = Callable[[str], str]


def _safe_parse_json(text: str) -> dict[str, Any]:
    """Attempt to parse JSON from the LLM response.

    LLMs sometimes wrap JSON in markdown code fences — strip those first.
    Falls back to returning the raw text in a dict if parsing fails.
    """
    cleaned = text.strip()
    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Drop first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM response was not valid JSON, returning raw text")
        return {"raw_response": text}


@register_task("summarize")
def summarize_document(
    document_text: str,
    doc_type: str,
    llm_caller: LLMCaller,
    prompt_loader: PromptLoader,
    task_config: AnalysisTaskConfig,
) -> dict[str, Any]:
    """Generate an executive summary of the document.

    Uses the doc-type-specific prompt template (e.g. ``rfp-summary.txt``)
    to produce a structured summary tailored to the document type.
    """
    # Render the prompt with the document text
    prompt = prompt_loader.render(
        task_config.prompt_template,
        document_text=document_text,
    )

    # Call GPT-4o
    response = llm_caller(prompt)
    result = _safe_parse_json(response)
    logger.info("Summarized %s document (%d chars)", doc_type, len(document_text))
    return result


@register_task("extract_clauses")
def extract_clauses(
    document_text: str,
    doc_type: str,
    llm_caller: LLMCaller,
    prompt_loader: PromptLoader,
    task_config: AnalysisTaskConfig,
) -> dict[str, Any]:
    """Extract and categorise clauses from a contract document.

    The contract-clauses prompt template asks GPT-4o to identify all
    clauses, their categories, risk levels, and negotiation points.
    """
    prompt = prompt_loader.render(
        task_config.prompt_template,
        document_text=document_text,
    )
    response = llm_caller(prompt)
    result = _safe_parse_json(response)
    logger.info("Extracted clauses from %s document", doc_type)
    return result


def identify_risks(
    analysis_output: dict[str, Any],
) -> list[RiskItem]:
    """Parse risk items from the LLM's analysis output.

    This is a post-processing step that converts the raw JSON ``risks``
    array into typed ``RiskItem`` models.  Works for any doc type because
    all prompt templates produce a ``risks`` array in the same format.
    """
    raw_risks = analysis_output.get("risks", [])
    items: list[RiskItem] = []
    for r in raw_risks:
        severity_str = r.get("severity", "medium").lower()
        try:
            severity = RiskSeverity(severity_str)
        except ValueError:
            severity = RiskSeverity.MEDIUM

        items.append(
            RiskItem(
                title=r.get("title", "Unknown Risk"),
                description=r.get("description", ""),
                severity=severity,
                recommendation=r.get("recommendation", ""),
            )
        )
    logger.info("Identified %d risks", len(items))
    return items


@register_task("compliance_check")
def check_compliance(
    document_text: str,
    doc_type: str,
    llm_caller: LLMCaller,
    prompt_loader: PromptLoader,
    task_config: AnalysisTaskConfig,
) -> dict[str, Any]:
    """Check a specification document for completeness and standards compliance.

    Uses the spec-compliance prompt template which asks GPT-4o to
    evaluate requirements clarity, acceptance criteria coverage, and
    standards alignment.
    """
    prompt = prompt_loader.render(
        task_config.prompt_template,
        document_text=document_text,
    )
    response = llm_caller(prompt)
    result = _safe_parse_json(response)
    logger.info("Compliance check complete for %s document", doc_type)
    return result


def build_analysis_result(
    document_id: str,
    doc_type: str,
    analysis_output: dict[str, Any],
) -> AnalysisResult:
    """Assemble an AnalysisResult from the raw LLM output.

    Extracts the summary and risks into the typed model that the rest
    of the pipeline consumes.
    """
    risks = identify_risks(analysis_output)
    summary = analysis_output.get("executive_summary", "") or analysis_output.get(
        "summary", ""
    )

    return AnalysisResult(
        document_id=document_id,
        doc_type=doc_type,
        summary=summary,
        risks=risks,
        metadata=analysis_output,
    )
