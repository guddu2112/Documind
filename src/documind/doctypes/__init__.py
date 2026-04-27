"""DocuMind document-type plugin system.

New document types are added by:
1. Dropping a YAML config in ``doctypes/types/``
2. (Optionally) adding a Pydantic model in ``core/models/``
3. (Optionally) adding a prompt template in ``agents/analysis/prompts/``
"""

from documind.doctypes.registry import DocTypeRegistry
from documind.doctypes.schema import DocumentTypeConfig

__all__ = ["DocTypeRegistry", "DocumentTypeConfig"]
