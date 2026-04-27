"""Agent Framework workflow — async pipeline using Microsoft Agent Framework.

This module wraps our four plain-Python executors (Ingestion, Extraction,
Analysis, Search) as Agent Framework ``Executor`` subclasses and wires
them into a sequential ``WorkflowBuilder`` graph.

Two deployment modes:
    1. ``DocumentPipeline`` (from workflow.py) — synchronous, for tests/CLI.
    2. ``build_agent_workflow()`` (this module) — async Agent Framework
       pipeline for Foundry-hosted deployment with streaming support.

Architecture::

    IngestionNode → ExtractionNode → AnalysisNode → SearchNode
                                                        │
                                                  yield_output(PipelineResult)

Each node wraps the existing executor, converting between the
Agent Framework's message-passing model and our typed dataclasses.
The ``FoundryChatClient`` is used by the AnalysisNode for LLM calls.

SDK version: agent-framework-core==1.0.0rc6
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from documind.agents.analysis.agent import AnalysisExecutor, AnalysisOutput
from documind.agents.extraction.agent import ExtractionExecutor, ExtractionOutput
from documind.agents.ingestion.agent import (
    IngestionExecutor,
    IngestionInput,
    IngestionOutput,
)
from documind.agents.orchestrator.workflow import PipelineResult
from documind.agents.search.agent import SearchExecutor, SearchOutput
from documind.core.models.base import ProcessingStatus

logger = logging.getLogger(__name__)


# ── Typed message envelope ─────────────────────────────────────────
# We pass this dict between Agent Framework nodes so each node knows
# the full pipeline state accumulated so far.

PipelineState = dict[str, Any]


def _make_state(
    file_bytes: bytes,
    filename: str,
    doc_type_hint: str | None = None,
) -> PipelineState:
    """Create the initial pipeline state dict that kicks off the workflow.

    This is the payload sent to the first node (IngestionNode).
    """
    return {
        "file_bytes": file_bytes,
        "filename": filename,
        "doc_type_hint": doc_type_hint,
        "stages_completed": [],
        "error": None,
    }


# ── Node 1: Ingestion ─────────────────────────────────────────────


class IngestionNode(Executor):
    """Agent Framework node that wraps the IngestionExecutor.

    Receives the raw file bytes and filename, runs classification and
    blob upload, then forwards the enriched state to ExtractionNode.
    """

    def __init__(
        self,
        ingestion_executor: IngestionExecutor,
        id: str = "IngestionNode",
    ) -> None:
        # Store executor reference before super().__init__ which may
        # freeze the instance in some Executor subclasses
        self._executor = ingestion_executor
        super().__init__(id=id)

    @handler
    async def handle(
        self, state: PipelineState, ctx: WorkflowContext[PipelineState]
    ) -> None:
        """Classify document, create record, upload to blob storage.

        On success, adds 'ingestion_output' to state and forwards it.
        On failure, marks the error and still forwards (so downstream
        nodes can yield the partial result).
        """
        try:
            inp = IngestionInput(
                file_bytes=state["file_bytes"],
                filename=state["filename"],
                doc_type_hint=state.get("doc_type_hint"),
            )
            output = self._executor.run(inp)

            state["ingestion_output"] = output
            state["stages_completed"].append("ingestion")
            logger.info("IngestionNode complete: id=%s", output.record.document_id)

        except Exception as exc:
            state["error"] = f"Failed at ingestion: {exc}"
            logger.error("IngestionNode failed: %s", exc, exc_info=True)

        await ctx.send_message(state)


# ── Node 2: Extraction ────────────────────────────────────────────


class ExtractionNode(Executor):
    """Agent Framework node that wraps the ExtractionExecutor.

    Receives ingestion output from the pipeline state, runs Document
    Intelligence, and forwards extraction results downstream.
    """

    def __init__(
        self,
        extraction_executor: ExtractionExecutor,
        id: str = "ExtractionNode",
    ) -> None:
        self._executor = extraction_executor
        super().__init__(id=id)

    @handler
    async def handle(
        self, state: PipelineState, ctx: WorkflowContext[PipelineState]
    ) -> None:
        """Run Document Intelligence on the ingested file.

        Skips processing if an earlier stage already failed (error is set).
        """
        # Short-circuit if a previous stage failed
        if state.get("error"):
            await ctx.send_message(state)
            return

        try:
            ingestion_output: IngestionOutput = state["ingestion_output"]
            output = self._executor.run(ingestion_output)

            state["extraction_output"] = output
            state["stages_completed"].append("extraction")
            logger.info("ExtractionNode complete: pages=%d", output.extraction.page_count)

        except Exception as exc:
            state["error"] = f"Failed at extraction: {exc}"
            logger.error("ExtractionNode failed: %s", exc, exc_info=True)

        await ctx.send_message(state)


# ── Node 3: Analysis ──────────────────────────────────────────────


class AnalysisNode(Executor):
    """Agent Framework node that wraps the AnalysisExecutor.

    Receives extraction output, runs GPT-4o analysis tasks defined in
    the doc-type config, and forwards the analysis results.
    """

    def __init__(
        self,
        analysis_executor: AnalysisExecutor,
        id: str = "AnalysisNode",
    ) -> None:
        self._executor = analysis_executor
        super().__init__(id=id)

    @handler
    async def handle(
        self, state: PipelineState, ctx: WorkflowContext[PipelineState]
    ) -> None:
        """Run LLM-based analysis (summarise, extract clauses, identify risks).

        Skips if a previous stage failed.
        """
        if state.get("error"):
            await ctx.send_message(state)
            return

        try:
            extraction_output: ExtractionOutput = state["extraction_output"]
            output = self._executor.run(extraction_output)

            state["analysis_output"] = output
            state["stages_completed"].append("analysis")
            logger.info(
                "AnalysisNode complete: risks=%d", len(output.analysis.risks)
            )

        except Exception as exc:
            state["error"] = f"Failed at analysis: {exc}"
            logger.error("AnalysisNode failed: %s", exc, exc_info=True)

        await ctx.send_message(state)


# ── Node 4: Search Indexing (terminal) ────────────────────────────


class SearchNode(Executor):
    """Agent Framework node that wraps the SearchExecutor.

    This is the terminal node — it yields the final PipelineResult
    via ``ctx.yield_output()`` so the workflow caller can collect it.
    """

    def __init__(
        self,
        search_executor: SearchExecutor,
        id: str = "SearchNode",
    ) -> None:
        self._executor = search_executor
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        state: PipelineState,
        ctx: WorkflowContext[None, PipelineResult],
    ) -> None:
        """Index the document into the search store and yield final result.

        Even if this stage fails, we yield a PipelineResult with partial
        data so the caller always gets a response.
        """
        search_output = None

        if not state.get("error"):
            try:
                analysis_output: AnalysisOutput = state["analysis_output"]
                search_output = self._executor.run(analysis_output)

                state["stages_completed"].append("search")
                logger.info("SearchNode complete: indexed=%s", search_output.document_id)

            except Exception as exc:
                state["error"] = f"Failed at search: {exc}"
                logger.error("SearchNode failed: %s", exc, exc_info=True)

        # Build the final result from accumulated state
        result = _build_result(state, search_output)
        await ctx.yield_output(result)


# ── Result builder ─────────────────────────────────────────────────


def _build_result(
    state: PipelineState,
    search_output: SearchOutput | None,
) -> PipelineResult:
    """Convert the accumulated pipeline state into a typed PipelineResult.

    This handles both success and partial-failure cases.
    """
    ingestion_out: IngestionOutput | None = state.get("ingestion_output")
    extraction_out: ExtractionOutput | None = state.get("extraction_output")
    analysis_out: AnalysisOutput | None = state.get("analysis_output")

    # Determine final status
    if state.get("error"):
        status = ProcessingStatus.FAILED
    else:
        status = ProcessingStatus.COMPLETED

    # Build record from ingestion output (or a placeholder if ingestion failed)
    from documind.core.models.base import DocumentRecord

    if ingestion_out:
        record = ingestion_out.record
    else:
        record = DocumentRecord(
            document_id="",
            doc_type="",
            source_filename=state.get("filename", ""),
        )

    return PipelineResult(
        document_id=record.document_id,
        status=status,
        record=record,
        extraction=extraction_out,
        analysis=analysis_out,
        search=search_output,
        error=state.get("error"),
        stages_completed=state.get("stages_completed", []),
    )


# ── Workflow builder ───────────────────────────────────────────────


def build_agent_workflow(
    ingestion_executor: IngestionExecutor,
    extraction_executor: ExtractionExecutor,
    analysis_executor: AnalysisExecutor,
    search_executor: SearchExecutor,
):
    """Build an Agent Framework Workflow from the four pipeline executors.

    Returns a ``Workflow`` object that can be run with::

        events = await workflow.run(initial_state)
        results = events.get_outputs()  # list[PipelineResult]

    Or streamed with::

        async for event in workflow.run(state, stream=True):
            ...

    The workflow is a linear chain:
        IngestionNode → ExtractionNode → AnalysisNode → SearchNode
    """
    # Create the four Agent Framework nodes, each wrapping our executor
    ingestion_node = IngestionNode(ingestion_executor)
    extraction_node = ExtractionNode(extraction_executor)
    analysis_node = AnalysisNode(analysis_executor)
    search_node = SearchNode(search_executor)

    # Wire them into a sequential pipeline using WorkflowBuilder
    # start_executor= sets the entry point; add_edge() defines directed edges
    workflow = (
        WorkflowBuilder(start_executor=ingestion_node)
        .add_edge(ingestion_node, extraction_node)
        .add_edge(extraction_node, analysis_node)
        .add_edge(analysis_node, search_node)
        .build()
    )

    logger.info("Built Agent Framework workflow: 4 nodes, 3 edges")
    return workflow
