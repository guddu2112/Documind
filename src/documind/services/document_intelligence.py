"""Azure Document Intelligence service wrapper.

Wraps the ``azure-ai-documentintelligence`` SDK to provide a clean
interface for the Extraction Agent.  Supports both prebuilt models
(layout, invoice, contract) and custom models.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from documind.core.config.settings import settings
from documind.core.models.base import ExtractedTable, KeyValuePair

logger = logging.getLogger(__name__)


def _default_client():
    """Build a DocumentIntelligenceClient from settings."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    if settings.azure_doc_intelligence_key:
        credential = AzureKeyCredential(settings.azure_doc_intelligence_key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    return DocumentIntelligenceClient(
        endpoint=settings.azure_doc_intelligence_endpoint,
        credential=credential,
    )


class DocumentIntelligenceService:
    """Wraps Azure Document Intelligence for layout analysis and extraction."""

    def __init__(self, client=None) -> None:
        # Dependency injection — pass None to use real Azure client
        self._client = client or _default_client()

    def analyze_document(
        self,
        file_bytes: bytes,
        model_id: str = "prebuilt-layout",
    ) -> dict[str, Any]:
        """Run Document Intelligence analysis and return the raw result dict.

        This is the low-level call; higher-level helpers below parse the
        result into our domain models.
        """
        # The SDK's begin_analyze_document returns a poller we must wait on
        poller = self._client.begin_analyze_document(
            model_id=model_id,
            body=file_bytes,
            content_type="application/octet-stream",
        )
        result = poller.result()
        logger.info(
            "Analysis complete — model=%s, pages=%d",
            model_id,
            len(result.pages) if hasattr(result, "pages") and result.pages else 0,
        )
        return result

    def extract_text(self, analysis_result) -> str:
        """Extract the full concatenated text from a Document Intelligence result."""
        if hasattr(analysis_result, "content"):
            return analysis_result.content or ""
        return ""

    def extract_key_value_pairs(self, analysis_result) -> list[KeyValuePair]:
        """Parse key-value pairs from the analysis result.

        Document Intelligence returns these for form-like documents
        (invoices, receipts, etc.).
        """
        pairs: list[KeyValuePair] = []
        kv_pairs = getattr(analysis_result, "key_value_pairs", None) or []
        for kvp in kv_pairs:
            key = kvp.key.content if kvp.key else ""
            value = kvp.value.content if kvp.value else ""
            confidence = getattr(kvp, "confidence", 0.0) or 0.0
            pairs.append(KeyValuePair(key=key, value=value, confidence=confidence))
        return pairs

    def extract_tables(self, analysis_result) -> list[ExtractedTable]:
        """Parse tables from the analysis result.

        Each table is returned with headers (first row) and subsequent
        data rows for easy downstream processing.
        """
        tables: list[ExtractedTable] = []
        raw_tables = getattr(analysis_result, "tables", None) or []
        for idx, table in enumerate(raw_tables):
            # Build a 2D grid from the cells
            row_count = table.row_count or 0
            col_count = table.column_count or 0
            grid = [["" for _ in range(col_count)] for _ in range(row_count)]

            for cell in (table.cells or []):
                r, c = cell.row_index, cell.column_index
                if r < row_count and c < col_count:
                    grid[r][c] = cell.content or ""

            # First row is treated as headers
            headers = grid[0] if grid else []
            rows = grid[1:] if len(grid) > 1 else []

            tables.append(
                ExtractedTable(
                    table_id=idx,
                    headers=headers,
                    rows=rows,
                    page=getattr(table, "bounding_regions", [{}])[0].get("page_number")
                    if getattr(table, "bounding_regions", None)
                    else None,
                )
            )
        return tables

    def get_page_count(self, analysis_result) -> int:
        """Return the number of pages in the analyzed document."""
        pages = getattr(analysis_result, "pages", None) or []
        return len(pages)
