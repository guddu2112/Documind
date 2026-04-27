# Analysis Agent Tools

from documind.agents.analysis.task_registry import TaskRegistry, register_task
from documind.agents.analysis.tools.tools import (
    build_analysis_result,
    check_compliance,
    extract_clauses,
    identify_risks,
    summarize_document,
)

__all__ = [
    "TaskRegistry",
    "build_analysis_result",
    "check_compliance",
    "extract_clauses",
    "identify_risks",
    "register_task",
    "summarize_document",
]
