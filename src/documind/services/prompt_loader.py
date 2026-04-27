"""Prompt template loader.

Loads Jinja2 templates from the ``agents/analysis/prompts/`` directory
and renders them with the provided context variables.  This keeps prompt
management declarative — add a ``.txt`` file to the prompts folder and
reference it from the doc-type YAML config.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

# Default directory where prompt templates live
_PROMPTS_DIR = Path(__file__).parent.parent / "agents" / "analysis" / "prompts"


class PromptLoader:
    """Loads and renders Jinja2 prompt templates."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or _PROMPTS_DIR
        # FileSystemLoader lets Jinja2 find templates by filename
        self._env = Environment(
            loader=FileSystemLoader(str(self._prompts_dir)),
            # Keep whitespace as-is so prompts read naturally
            keep_trailing_newline=True,
            trim_blocks=False,
        )

    def render(self, template_name: str, **context) -> str:
        """Render *template_name* with the given context variables.

        Raises ``TemplateNotFound`` if the file doesn't exist.

        Example::

            loader = PromptLoader()
            prompt = loader.render("rfp-summary.txt", document_text="...")
        """
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound:
            logger.error("Prompt template not found: %s", template_name)
            raise

        rendered = template.render(**context)
        logger.debug("Rendered template %s (%d chars)", template_name, len(rendered))
        return rendered

    def list_templates(self) -> list[str]:
        """Return all available template filenames."""
        return sorted(self._env.list_templates())
