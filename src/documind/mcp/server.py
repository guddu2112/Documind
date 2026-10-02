"""DocuMind MCP Server — analysis tools for AI assistants.

Exposes the DocuMind analysis pipeline as MCP tools so that external
AI assistants (Copilot, Claude, etc.) can call them over the Model
Context Protocol.

Tools exposed:
    - **list_doc_types**   — enumerate configured document types
    - **summarize**        — generate an executive summary
    - **extract_clauses**  — extract and categorise contract clauses
    - **check_compliance** — check spec compliance

Run with::

    python -m documind.mcp.server          # stdio transport (default)
    python -m documind.mcp.server --sse    # SSE transport for web clients
"""

from __future__ import annotations

import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from documind.agents.analysis.task_registry import TaskRegistry

# Import tools to trigger @register_task decorators
import documind.agents.analysis.tools.tools  # noqa: F401
from documind.doctypes.registry import DocTypeRegistry
from documind.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

# ── Bootstrap shared dependencies ───────────────────────────────

_registry = DocTypeRegistry()
_registry.load()

_prompt_loader = PromptLoader()


def _get_llm_caller():
    """Build the LLM caller from environment settings.

    Delegates to :mod:`documind.services.factory` so it follows the
    ``settings.backend = "azure" | "local"`` switch.
    """
    from documind.services import factory

    return factory.get_llm_caller()


# ── MCP Server ──────────────────────────────────────────────────

mcp = FastMCP(
    "DocuMind",
    instructions=(
        "DocuMind is an intelligent document processing pipeline. "
        "Use these tools to analyse documents: summarize them, "
        "extract contract clauses, or check spec compliance. "
        "Call list_doc_types first to see which document types are supported."
    ),
)


@mcp.tool()
def list_doc_types() -> str:
    """List all configured document types and their analysis tasks.

    Returns a JSON array of objects with name, display_name, description,
    supported_formats, and analysis_tasks for each document type.
    """
    types = []
    for dt in _registry.list_enabled():
        types.append({
            "name": dt.name,
            "display_name": dt.display_name,
            "description": dt.description,
            "supported_formats": [f.value for f in dt.supported_formats],
            "analysis_tasks": [
                {"name": t.name, "description": t.description}
                for t in dt.analysis_tasks
            ],
        })
    return json.dumps(types, indent=2)


@mcp.tool()
def summarize(document_text: str, doc_type: str = "rfp") -> str:
    """Generate an executive summary of a document.

    Args:
        document_text: The full text of the document to summarize.
        doc_type: Document type (e.g. 'rfp', 'contract', 'spec').
                  Determines which prompt template is used.

    Returns:
        JSON string with executive_summary and risks.
    """
    return _run_analysis_task("summarize", document_text, doc_type)


@mcp.tool()
def extract_clauses(document_text: str, doc_type: str = "contract") -> str:
    """Extract and categorise clauses from a contract document.

    Args:
        document_text: The full text of the contract.
        doc_type: Document type (defaults to 'contract').

    Returns:
        JSON string with extracted clauses, categories, and risk levels.
    """
    return _run_analysis_task("extract_clauses", document_text, doc_type)


@mcp.tool()
def check_compliance(document_text: str, doc_type: str = "spec") -> str:
    """Check a specification document for completeness and standards compliance.

    Args:
        document_text: The full text of the specification.
        doc_type: Document type (defaults to 'spec').

    Returns:
        JSON string with compliance assessment and recommendations.
    """
    return _run_analysis_task("compliance_check", document_text, doc_type)


def _run_analysis_task(task_name: str, document_text: str, doc_type: str) -> str:
    """Internal helper — look up a registered task and execute it."""
    tool_fn = TaskRegistry.get(task_name)
    if tool_fn is None:
        return json.dumps({"error": f"Unknown analysis task: {task_name}"})

    # Resolve the task config from the doc-type registry
    try:
        doc_config = _registry.get(doc_type)
    except KeyError:
        return json.dumps({"error": f"Unknown doc_type: {doc_type}"})

    # Find the matching task config
    task_config = next(
        (t for t in doc_config.analysis_tasks if t.name == task_name),
        None,
    )
    if task_config is None:
        return json.dumps({
            "error": f"Doc type '{doc_type}' has no task '{task_name}'. "
            f"Available tasks: {[t.name for t in doc_config.analysis_tasks]}"
        })

    llm_caller = _get_llm_caller()
    result = tool_fn(
        document_text=document_text,
        doc_type=doc_type,
        llm_caller=llm_caller,
        prompt_loader=_prompt_loader,
        task_config=task_config,
    )
    return json.dumps(result, indent=2)


# ── Entry point ─────────────────────────────────────────────────


def main():
    """Run the MCP server.

    Transports:
        (default)   stdio   — for CLI / VS Code integration
        --sse       SSE     — legacy Server-Sent Events transport
        --http      Streamable HTTP — modern transport (Inspector v0.21+)
    """
    if "--http" in sys.argv:
        transport = "streamable-http"
    elif "--sse" in sys.argv:
        transport = "sse"
    else:
        transport = "stdio"

    if transport in ("sse", "streamable-http"):
        from starlette.middleware.cors import CORSMiddleware

        if transport == "streamable-http":
            app = mcp.streamable_http_app()
        else:
            app = mcp.sse_app()

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
