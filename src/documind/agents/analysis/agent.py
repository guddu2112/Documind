"""Analysis Agent — workflow executor.

This is the GPT-4o-powered agent.  It receives extraction output,
looks up the analysis tasks defined in the doc-type config, and runs
each task's prompt template through the LLM.

The ``llm_caller`` dependency is injected so the executor can be tested
with a mock LLM.  In production, it wraps the ``FoundryChatClient``
from the Microsoft Agent Framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from documind.agents.analysis.tools.tools import (
    build_analysis_result,
    check_compliance,
    extract_clauses,
    summarize_document,
)
from documind.agents.extraction.agent import ExtractionOutput
from documind.core.models.base import AnalysisResult
from documind.doctypes.registry import DocTypeRegistry
from documind.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

# Type alias — same as in tools.py
LLMCaller = Callable[[str], str]

# Map analysis task names → tool functions.
# When a doc-type config lists an analysis task by name, we dispatch
# to the matching function here.
_TASK_DISPATCH: dict[str, Callable] = {
    "summarize": summarize_document,
    "extract_clauses": extract_clauses,
    "compliance_check": check_compliance,
}


@dataclass
class AnalysisOutput:
    """Output produced by the Analysis Executor."""
    analysis: AnalysisResult
    extraction: ExtractionOutput  # carry forward for indexing


class AnalysisExecutor:
    """Analysis workflow step — run LLM-based analysis per doc-type config.

    For each ``analysis_task`` defined in the doc-type YAML config, the
    executor finds the matching tool function, renders the prompt, and
    calls GPT-4o.  Results are merged into a single ``AnalysisResult``.
    """

    def __init__(
        self,
        registry: DocTypeRegistry,
        prompt_loader: PromptLoader,
        llm_caller: LLMCaller,
    ) -> None:
        self._registry = registry
        self._prompt_loader = prompt_loader
        self._llm_caller = llm_caller

    def run(self, inp: ExtractionOutput) -> AnalysisOutput:
        """Execute analysis on the extracted document text.

        1. Look up the analysis tasks from the doc-type config.
        2. For each task, dispatch to the correct tool function.
        3. Merge all outputs into a single ``AnalysisResult``.
        """
        doc_config = self._registry.get(inp.extraction.doc_type)
        document_text = inp.extraction.raw_text
        doc_type = inp.extraction.doc_type

        # Accumulate outputs from all analysis tasks
        merged_output: dict[str, Any] = {}

        for task in doc_config.analysis_tasks:
            tool_fn = _TASK_DISPATCH.get(task.name)
            if tool_fn is None:
                logger.warning(
                    "No tool registered for analysis task '%s' — skipping",
                    task.name,
                )
                continue

            logger.info(
                "Running analysis task '%s' for doc_type=%s", task.name, doc_type
            )
            task_output = tool_fn(
                document_text=document_text,
                doc_type=doc_type,
                llm_caller=self._llm_caller,
                prompt_loader=self._prompt_loader,
                task_config=task,
            )
            # Merge each task's output into the combined result
            merged_output.update(task_output)

        # Build the final typed result
        analysis = build_analysis_result(
            document_id=inp.extraction.document_id,
            doc_type=doc_type,
            analysis_output=merged_output,
        )

        logger.info(
            "Analysis complete: id=%s risks=%d summary_len=%d",
            analysis.document_id,
            len(analysis.risks),
            len(analysis.summary),
        )
        return AnalysisOutput(analysis=analysis, extraction=inp)
