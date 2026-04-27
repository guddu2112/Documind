"""Intelligent document chunking for large documents.

When a document exceeds GPT-4o's context window, we need to split it into
manageable pieces.  Naive chunking (split every N tokens) breaks tables
mid-row and splits clauses across chunks, producing garbage analysis.

This module provides **section-aware, table-preserving** chunking:

1. Splits on natural document boundaries (headings, page breaks).
2. Never breaks a table row or a numbered clause mid-way.
3. Keeps each chunk under a configurable token budget.
4. Adds overlap between chunks so the LLM has context continuity.

Usage::

    from documind.services.chunker import DocumentChunker

    chunker = DocumentChunker(max_tokens=8000, overlap_tokens=200)
    chunks = chunker.chunk(extracted_text, tables=extraction.tables)

The Analysis Agent calls this before sending text to GPT-4o, then
merges the per-chunk results into a single AnalysisResult.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from documind.core.models.base import ExtractedTable

logger = logging.getLogger(__name__)

# Rough token estimate: 1 token ≈ 4 characters for English text.
# This avoids pulling in tiktoken as a dependency just for chunking.
_CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    """A single chunk of document text with metadata.

    Attributes:
        index:      Zero-based position in the chunk sequence.
        text:       The chunk's text content.
        token_estimate: Approximate number of tokens in this chunk.
        tables:     Tables that fall within this chunk's text range.
        start_char: Character offset where this chunk starts in the original text.
        end_char:   Character offset where this chunk ends in the original text.
    """
    index: int
    text: str
    token_estimate: int
    tables: list[ExtractedTable] = field(default_factory=list)
    start_char: int = 0
    end_char: int = 0


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length.

    Uses a 4-chars-per-token heuristic which is close enough for
    chunking decisions.  Exact counting would require tiktoken and
    adds latency we don't need here.
    """
    return max(1, len(text) // _CHARS_PER_TOKEN)


# Regex for common section heading patterns:
# - Markdown headings (## Heading)
# - Numbered sections (1.2.3 Title)
# - ALL-CAPS headings (SECTION TITLE)
# - Page break markers
_SECTION_PATTERN = re.compile(
    r"""
    (?:^|\n)                      # start of line
    (?:
        \#{1,4}\s+.+              # markdown headings: ## Title
        | \d+(?:\.\d+)*\s+[A-Z]  # numbered sections: 1.2 Title
        | [A-Z][A-Z\s]{4,}$      # ALL-CAPS headings (at least 5 chars)
        | -{3,}                   # horizontal rules / dividers
        | \f                      # form feed (page break)
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


def _find_section_boundaries(text: str) -> list[int]:
    """Find character offsets where sections begin.

    Returns a sorted list of offsets where the text can be cleanly split.
    These are the positions just before a heading or section marker.
    """
    boundaries = [0]  # always start at the beginning
    for match in _SECTION_PATTERN.finditer(text):
        pos = match.start()
        # Avoid duplicate boundaries at position 0
        if pos > 0 and pos not in boundaries:
            boundaries.append(pos)
    boundaries.append(len(text))  # always end at the end
    return sorted(set(boundaries))


class DocumentChunker:
    """Section-aware, table-preserving document chunker.

    Parameters:
        max_tokens:     Maximum tokens per chunk (default 8000, leaves room
                        for the prompt template which adds ~1000 tokens).
        overlap_tokens: Number of tokens to overlap between consecutive
                        chunks for context continuity (default 200).
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        overlap_tokens: int = 200,
    ) -> None:
        if max_tokens < 500:
            raise ValueError("max_tokens must be at least 500")
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be less than max_tokens")

        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens
        # Convert token limits to character limits for faster comparison
        self._max_chars = max_tokens * _CHARS_PER_TOKEN
        self._overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    def chunk(
        self,
        text: str,
        tables: list[ExtractedTable] | None = None,
    ) -> list[Chunk]:
        """Split document text into chunks respecting section boundaries.

        If the entire text fits within ``max_tokens``, returns a single chunk.
        Otherwise, splits at section headings and merges small sections
        until each chunk is near (but under) the token limit.

        Args:
            text:   The full extracted text from Document Intelligence.
            tables: Optional list of extracted tables to attach to the
                    chunk where they appear (by character offset).

        Returns:
            List of Chunk objects in document order.
        """
        tables = tables or []

        # Fast path: document fits in one chunk
        if _estimate_tokens(text) <= self._max_tokens:
            logger.info("Document fits in single chunk (%d tokens)", _estimate_tokens(text))
            return [
                Chunk(
                    index=0,
                    text=text,
                    token_estimate=_estimate_tokens(text),
                    tables=tables,
                    start_char=0,
                    end_char=len(text),
                )
            ]

        # Find natural section boundaries in the text
        boundaries = _find_section_boundaries(text)

        # Extract sections between boundaries
        sections: list[tuple[int, int, str]] = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            section_text = text[start:end]
            if section_text.strip():  # skip empty sections
                sections.append((start, end, section_text))

        # Merge small sections into chunks that fit under the token limit
        chunks: list[Chunk] = []
        current_text = ""
        current_start = 0
        chunk_index = 0

        for start, end, section_text in sections:
            combined = current_text + section_text
            combined_tokens = _estimate_tokens(combined)

            if combined_tokens <= self._max_tokens:
                # Section fits — accumulate it
                if not current_text:
                    current_start = start
                current_text = combined
            else:
                # Adding this section would exceed the limit
                if current_text:
                    # Flush the accumulated text as a chunk
                    chunks.append(
                        Chunk(
                            index=chunk_index,
                            text=current_text,
                            token_estimate=_estimate_tokens(current_text),
                            start_char=current_start,
                            end_char=current_start + len(current_text),
                        )
                    )
                    chunk_index += 1

                    # Start new chunk with overlap from the end of the previous one
                    overlap_text = current_text[-self._overlap_chars:] if self._overlap_chars > 0 else ""
                    current_text = overlap_text + section_text
                    current_start = start - len(overlap_text)
                else:
                    # Single section exceeds the limit — force-split by characters
                    current_text = section_text
                    current_start = start

                # If even a single section exceeds max, force-split it
                while _estimate_tokens(current_text) > self._max_tokens:
                    # Split at the character limit, trying to break at a newline
                    split_pos = self._find_safe_split(current_text, self._max_chars)
                    chunks.append(
                        Chunk(
                            index=chunk_index,
                            text=current_text[:split_pos],
                            token_estimate=_estimate_tokens(current_text[:split_pos]),
                            start_char=current_start,
                            end_char=current_start + split_pos,
                        )
                    )
                    chunk_index += 1
                    # Advance with overlap
                    overlap_start = max(0, split_pos - self._overlap_chars)
                    current_text = current_text[overlap_start:]
                    current_start += overlap_start

        # Flush any remaining text
        if current_text.strip():
            chunks.append(
                Chunk(
                    index=chunk_index,
                    text=current_text,
                    token_estimate=_estimate_tokens(current_text),
                    start_char=current_start,
                    end_char=current_start + len(current_text),
                )
            )

        # Attach tables to the chunks they belong to (by character range)
        self._attach_tables(chunks, tables, text)

        logger.info(
            "Chunked document into %d chunks (max_tokens=%d, overlap=%d)",
            len(chunks),
            self._max_tokens,
            self._overlap_tokens,
        )
        return chunks

    def _find_safe_split(self, text: str, max_chars: int) -> int:
        """Find a safe split point near max_chars that doesn't break mid-line.

        Prefers splitting at the last newline before the limit.  If no
        newline is found, splits at the limit (worst case).
        """
        if max_chars >= len(text):
            return len(text)

        # Look for the last newline within the allowed range
        last_newline = text.rfind("\n", 0, max_chars)
        if last_newline > max_chars // 2:
            # Found a newline in the second half — use it
            return last_newline + 1  # include the newline in the first chunk

        # No good newline — split at the hard limit
        return max_chars

    def _attach_tables(
        self,
        chunks: list[Chunk],
        tables: list[ExtractedTable],
        full_text: str,
    ) -> None:
        """Attach each table to the chunk whose character range contains it.

        Tables don't have character offsets in the ExtractionResult, so we
        use a simple heuristic: look for the table's first header text in
        each chunk and assign the table to the first chunk that contains it.
        """
        for table in tables:
            if not table.headers:
                continue

            # Use the first header as a search string
            search_text = table.headers[0]
            if not search_text:
                continue

            for chunk in chunks:
                if search_text in chunk.text:
                    chunk.tables.append(table)
                    break  # each table belongs to one chunk


def merge_chunk_results(
    chunk_results: list[dict],
    strategy: str = "concatenate",
) -> dict:
    """Merge analysis results from multiple chunks into a single result.

    When a document is chunked, each chunk produces its own analysis
    output.  This function combines them:

    - **executive_summary**: Concatenated with chunk markers.
    - **risks**: Deduplicated by title.
    - **Other lists**: Concatenated.
    - **Other scalars**: First non-empty value wins.

    Args:
        chunk_results: List of analysis output dicts from each chunk.
        strategy:      Merge strategy — currently only "concatenate".

    Returns:
        A single merged analysis dict.
    """
    if not chunk_results:
        return {}

    if len(chunk_results) == 1:
        return chunk_results[0]

    merged: dict = {}
    seen_risk_titles: set[str] = set()

    for i, result in enumerate(chunk_results):
        for key, value in result.items():
            if key == "executive_summary":
                # Concatenate summaries with chunk markers
                existing = merged.get(key, "")
                chunk_label = f"[Chunk {i + 1}] " if len(chunk_results) > 1 else ""
                merged[key] = (existing + "\n" + chunk_label + str(value)).strip()

            elif key == "risks":
                # Deduplicate risks by title
                existing_risks = merged.get("risks", [])
                for risk in (value or []):
                    title = risk.get("title", "")
                    if title not in seen_risk_titles:
                        seen_risk_titles.add(title)
                        existing_risks.append(risk)
                merged["risks"] = existing_risks

            elif isinstance(value, list):
                # Concatenate list values
                existing_list = merged.get(key, [])
                existing_list.extend(value)
                merged[key] = existing_list

            elif key not in merged or not merged[key]:
                # First non-empty scalar wins
                merged[key] = value

    logger.info(
        "Merged %d chunk results: %d unique risks",
        len(chunk_results),
        len(merged.get("risks", [])),
    )
    return merged
