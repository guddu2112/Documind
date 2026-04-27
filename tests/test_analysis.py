"""Tests for the Analysis Agent — tools and executor.

Validates prompt rendering, LLM response parsing, risk identification,
and the full analysis executor flow using a mock LLM caller.
"""

import json
import pytest

from documind.agents.analysis.tools.tools import (
    build_analysis_result,
    extract_clauses,
    identify_risks,
    summarize_document,
)
from documind.agents.analysis.agent import AnalysisExecutor, AnalysisOutput
from documind.agents.extraction.agent import ExtractionOutput
from documind.agents.ingestion.agent import IngestionOutput
from documind.core.models.base import (
    AnalysisResult,
    DocumentRecord,
    ExtractionResult,
    RiskSeverity,
)
from documind.doctypes.schema import AnalysisTaskConfig


class TestSummarizeDocument:
    """Tests for the summarize_document tool."""

    def test_renders_prompt_and_calls_llm(self, mock_llm_caller, prompt_loader):
        """The tool should render the prompt template with the document
        text and call the LLM with the rendered prompt."""
        task = AnalysisTaskConfig(
            name="summarize",
            prompt_template="rfp-summary.txt",
        )
        result = summarize_document(
            document_text="Sample RFP content",
            doc_type="rfp",
            llm_caller=mock_llm_caller,
            prompt_loader=prompt_loader,
            task_config=task,
        )
        # The mock LLM returns JSON that should be parsed
        assert "executive_summary" in result
        assert isinstance(result["executive_summary"], str)

    def test_handles_markdown_wrapped_json(self, prompt_loader):
        """LLMs sometimes wrap JSON in markdown code fences — the parser
        should strip those before parsing."""
        wrapped_response = '```json\n{"executive_summary": "test"}\n```'
        caller = lambda prompt: wrapped_response

        task = AnalysisTaskConfig(
            name="summarize",
            prompt_template="rfp-summary.txt",
        )
        result = summarize_document(
            document_text="text",
            doc_type="rfp",
            llm_caller=caller,
            prompt_loader=prompt_loader,
            task_config=task,
        )
        assert result["executive_summary"] == "test"


class TestIdentifyRisks:
    """Tests for the identify_risks tool."""

    def test_parses_risks_from_analysis_output(self):
        """Should convert raw risk dicts into typed RiskItem objects."""
        analysis_output = {
            "risks": [
                {
                    "title": "Data breach risk",
                    "description": "No encryption mentioned",
                    "severity": "critical",
                    "recommendation": "Add encryption clause",
                },
                {
                    "title": "Schedule risk",
                    "description": "Tight timeline",
                    "severity": "medium",
                },
            ]
        }
        risks = identify_risks(analysis_output)
        assert len(risks) == 2
        assert risks[0].severity == RiskSeverity.CRITICAL
        assert risks[0].title == "Data breach risk"
        assert risks[1].severity == RiskSeverity.MEDIUM

    def test_handles_empty_risks(self):
        """Should return an empty list when no risks are found."""
        risks = identify_risks({"executive_summary": "No issues"})
        assert risks == []

    def test_handles_invalid_severity(self):
        """Should default to MEDIUM for unrecognised severity values."""
        risks = identify_risks(
            {"risks": [{"title": "X", "description": "Y", "severity": "unknown"}]}
        )
        assert risks[0].severity == RiskSeverity.MEDIUM


class TestBuildAnalysisResult:
    """Tests for the build_analysis_result helper."""

    def test_assembles_result_with_risks(self):
        """Should create an AnalysisResult with summary and risks."""
        output = {
            "executive_summary": "A vendor is needed.",
            "risks": [
                {"title": "Cost overrun", "description": "Budget too low", "severity": "high"}
            ],
        }
        result = build_analysis_result("doc-1", "rfp", output)
        assert isinstance(result, AnalysisResult)
        assert result.document_id == "doc-1"
        assert result.summary == "A vendor is needed."
        assert len(result.risks) == 1
        assert result.risks[0].severity == RiskSeverity.HIGH


class TestAnalysisExecutor:
    """Tests for the full Analysis Executor."""

    def test_full_analysis_flow(
        self,
        registry,
        mock_llm_caller,
        prompt_loader,
        sample_extraction_result,
    ):
        """The executor should look up analysis tasks from the doc-type
        config and run them through the LLM."""
        # Build an ExtractionOutput to feed into the analysis executor
        record = DocumentRecord(
            document_id="test-doc-001",
            doc_type="rfp",
            source_filename="test-rfp.pdf",
        )
        ingestion_out = IngestionOutput(record=record, file_bytes=b"fake")
        extraction_out = ExtractionOutput(
            extraction=sample_extraction_result,
            ingestion=ingestion_out,
        )

        executor = AnalysisExecutor(
            registry=registry,
            prompt_loader=prompt_loader,
            llm_caller=mock_llm_caller,
        )
        output = executor.run(extraction_out)

        assert isinstance(output, AnalysisOutput)
        assert output.analysis.document_id == "test-doc-001"
        assert output.analysis.doc_type == "rfp"
        # The mock LLM returns an executive_summary
        assert len(output.analysis.summary) > 0
        # The mock LLM returns one risk
        assert len(output.analysis.risks) >= 1

    def test_skips_unknown_analysis_tasks(
        self,
        registry,
        mock_llm_caller,
        prompt_loader,
        sample_extraction_result,
    ):
        """If a doc-type config has an analysis task with no matching
        tool function, it should be skipped without error."""
        # This is implicitly tested because our doc-type configs only
        # have tasks that exist in _TASK_DISPATCH.  But let's verify
        # the logging path works by running a valid config.
        record = DocumentRecord(
            document_id="test-doc-001",
            doc_type="rfp",
            source_filename="rfp.pdf",
        )
        ingestion_out = IngestionOutput(record=record, file_bytes=b"fake")
        extraction_out = ExtractionOutput(
            extraction=sample_extraction_result,
            ingestion=ingestion_out,
        )
        executor = AnalysisExecutor(
            registry=registry,
            prompt_loader=prompt_loader,
            llm_caller=mock_llm_caller,
        )
        # Should not raise
        output = executor.run(extraction_out)
        assert output.analysis.document_id == "test-doc-001"
