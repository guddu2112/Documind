"""Extraction Agent function tools.

These functions wrap Azure Document Intelligence to extract structured
data from documents.  Three tools corresponding to the plan:

1. **extract_layout**          — run Document Intelligence and get raw text
2. **extract_key_value_pairs** — parse key-value pairs from the result
3. **extract_tables**          — parse tables from the result

All tools take a Document Intelligence ``analysis_result`` (the raw
response from the SDK) so they can be called independently or chained.
"""

from __future__ import annotations

import logging
from typing import Any

from documind.core.models.base import (
    ExtractionResult,
    ExtractedTable,
    KeyValuePair,
)
from documind.services.document_intelligence import DocumentIntelligenceService

logger = logging.getLogger(__name__)


def extract_layout(
    file_bytes: bytes,
    model_id: str,
    di_service: DocumentIntelligenceService,
) -> Any:
    """Run Document Intelligence analysis on raw file bytes.

    Returns the SDK's analysis result object which contains pages,
    text, tables, key-value pairs, etc.

    *model_id* comes from the doc-type config (e.g. "prebuilt-layout",
    "prebuilt-contract").
    """
    logger.info("Running Document Intelligence model=%s", model_id)
    result = di_service.analyze_document(file_bytes=file_bytes, model_id=model_id)
    return result


def extract_key_value_pairs(
    analysis_result: Any,
    di_service: DocumentIntelligenceService,
) -> list[KeyValuePair]:
    """Extract key-value pairs from a Document Intelligence result.

    Key-value pairs are found in forms, invoices, and other structured
    documents where the layout has labelled fields.
    """
    pairs = di_service.extract_key_value_pairs(analysis_result)
    logger.info("Extracted %d key-value pairs", len(pairs))
    return pairs


def extract_tables(
    analysis_result: Any,
    di_service: DocumentIntelligenceService,
) -> list[ExtractedTable]:
    """Extract tables from a Document Intelligence result.

    Each table is returned with headers and rows for easy downstream
    consumption (e.g. feeding into GPT-4o for analysis).
    """
    tables = di_service.extract_tables(analysis_result)
    logger.info("Extracted %d tables", len(tables))
    return tables


def build_extraction_result(
    document_id: str,
    doc_type: str,
    source_filename: str,
    analysis_result: Any,
    di_service: DocumentIntelligenceService,
) -> ExtractionResult:
    """Compose all extraction outputs into a single ExtractionResult.

    This is a convenience function that calls the three individual tools
    and assembles the result model used by the rest of the pipeline.
    """
    raw_text = di_service.extract_text(analysis_result)
    kv_pairs = extract_key_value_pairs(analysis_result, di_service)
    tables = extract_tables(analysis_result, di_service)
    page_count = di_service.get_page_count(analysis_result)

    return ExtractionResult(
        document_id=document_id,
        doc_type=doc_type,
        source_filename=source_filename,
        page_count=page_count,
        raw_text=raw_text,
        key_value_pairs=kv_pairs,
        tables=tables,
        # Confidence is the average of KV pair confidences (0 if none)
        confidence_score=(
            sum(p.confidence for p in kv_pairs) / len(kv_pairs)
            if kv_pairs
            else 0.0
        ),
    )
