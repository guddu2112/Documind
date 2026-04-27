# DocuMind Agents
#
# Five agents form the document processing pipeline:
#   Ingestion → Extraction → Analysis → Search
#   coordinated by the Orchestrator.
#
# Each agent is an Executor with injectable service dependencies.
# The Orchestrator wires them into a sequential pipeline.

from documind.agents.analysis import AnalysisExecutor, AnalysisOutput
from documind.agents.extraction import ExtractionExecutor, ExtractionOutput
from documind.agents.ingestion import IngestionExecutor, IngestionInput, IngestionOutput
from documind.agents.orchestrator import DocumentPipeline, PipelineResult
from documind.agents.search import SearchExecutor, SearchOutput

__all__ = [
    "AnalysisExecutor",
    "AnalysisOutput",
    "DocumentPipeline",
    "ExtractionExecutor",
    "ExtractionOutput",
    "IngestionExecutor",
    "IngestionInput",
    "IngestionOutput",
    "PipelineResult",
    "SearchExecutor",
    "SearchOutput",
]
