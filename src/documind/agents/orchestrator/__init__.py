# Orchestrator - Pipeline workflow coordinator
#
# Two execution modes:
#   1. DocumentPipeline — synchronous, for tests/CLI (Phase 1)
#   2. build_agent_workflow — async Agent Framework pipeline (Phase 2)

from documind.agents.orchestrator.workflow import DocumentPipeline, PipelineResult

__all__ = ["DocumentPipeline", "PipelineResult"]
