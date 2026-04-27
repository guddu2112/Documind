"""Document-type registry.

Auto-discovers YAML configs in the ``types/`` directory, validates each
against :class:`DocumentTypeConfig`, and provides O(1) lookup by name.

Usage::

    from documind.doctypes import DocTypeRegistry

    registry = DocTypeRegistry()
    registry.load()                       # discovers all YAML configs

    rfp = registry.get("rfp")             # returns DocumentTypeConfig
    all_types = registry.list_enabled()   # returns only enabled types
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from documind.doctypes.schema import DocumentTypeConfig

logger = logging.getLogger(__name__)

_TYPES_DIR = Path(__file__).parent / "types"


class DocTypeRegistry:
    """Singleton-style registry for document-type configurations."""

    def __init__(self, types_dir: Path | None = None) -> None:
        self._types_dir = types_dir or _TYPES_DIR
        self._registry: dict[str, DocumentTypeConfig] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Scan the types directory and load all ``*.yaml`` / ``*.yml`` files."""
        if not self._types_dir.is_dir():
            logger.warning("Doc-type directory does not exist: %s", self._types_dir)
            return

        for path in sorted(self._types_dir.glob("*.y*ml")):
            try:
                self._load_file(path)
            except Exception:
                logger.exception("Failed to load doc-type config: %s", path.name)

    def _load_file(self, path: Path) -> None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            logger.warning("Empty config file skipped: %s", path.name)
            return

        config = DocumentTypeConfig.model_validate(raw)

        if config.name in self._registry:
            logger.warning(
                "Duplicate doc-type name '%s' in %s — overwriting previous.",
                config.name,
                path.name,
            )

        self._registry[config.name] = config
        logger.info("Loaded doc-type: %s (%s)", config.name, path.name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str) -> DocumentTypeConfig:
        """Return config for *name* or raise ``KeyError``."""
        return self._registry[name]

    def list_all(self) -> list[DocumentTypeConfig]:
        """Return all registered doc-type configs (including disabled)."""
        return list(self._registry.values())

    def list_enabled(self) -> list[DocumentTypeConfig]:
        """Return only enabled doc-type configs."""
        return [c for c in self._registry.values() if c.enabled]

    def names(self) -> list[str]:
        """Return sorted list of registered doc-type names."""
        return sorted(self._registry.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)
