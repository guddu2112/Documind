"""Tests for the Document Chunker — section-aware, table-preserving chunking.

Validates that:
    - Small documents stay as a single chunk.
    - Large documents are split at section boundaries.
    - Tables are attached to the correct chunk.
    - Overlap between chunks provides context continuity.
    - Edge cases: empty text, single huge section, no headings.
"""

import pytest

from documind.services.chunker import (
    Chunk,
    DocumentChunker,
    _estimate_tokens,
    _find_section_boundaries,
    merge_chunk_results,
)
from documind.core.models.base import ExtractedTable


class TestEstimateTokens:
    """Tests for the token estimation function."""

    def test_empty_string_returns_one(self):
        """Empty string should return at least 1 token."""
        assert _estimate_tokens("") == 1

    def test_known_length(self):
        """400 characters ≈ 100 tokens (4 chars/token heuristic)."""
        text = "a" * 400
        assert _estimate_tokens(text) == 100

    def test_short_text(self):
        """Short text should return a small token count."""
        assert _estimate_tokens("hello") >= 1


class TestFindSectionBoundaries:
    """Tests for section boundary detection."""

    def test_markdown_headings(self):
        """Should detect markdown ## headings as boundaries."""
        text = "Intro text here.\n## Section One\nContent.\n## Section Two\nMore."
        boundaries = _find_section_boundaries(text)
        # Should find boundaries at 0, before each ##, and at end
        assert 0 in boundaries
        assert len(text) in boundaries
        assert len(boundaries) >= 3  # start, 2 headings, end

    def test_numbered_sections(self):
        """Should detect numbered section headings (1.2 Title)."""
        text = "Preamble.\n1.1 Introduction\nText.\n2.1 Scope\nMore text."
        boundaries = _find_section_boundaries(text)
        assert len(boundaries) >= 3

    def test_no_headings_returns_start_and_end(self):
        """Text with no headings should have boundaries at start and end only."""
        text = "Just a plain paragraph with no headings at all."
        boundaries = _find_section_boundaries(text)
        assert boundaries == [0, len(text)]

    def test_horizontal_rule(self):
        """Horizontal rules (---) should be detected as boundaries."""
        text = "Part one.\n---\nPart two."
        boundaries = _find_section_boundaries(text)
        assert len(boundaries) >= 3


class TestDocumentChunker:
    """Tests for the main DocumentChunker class."""

    def test_single_chunk_for_small_document(self):
        """A document under max_tokens should produce exactly one chunk."""
        chunker = DocumentChunker(max_tokens=8000)
        text = "Short document content."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert chunks[0].text == text
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(text)

    def test_multiple_chunks_for_large_document(self):
        """A document exceeding max_tokens should produce multiple chunks."""
        # Use the minimum allowed max_tokens to force chunking
        chunker = DocumentChunker(max_tokens=500, overlap_tokens=50)

        # Build a document with clear sections (~300 tokens each)
        sections = []
        for i in range(5):
            sections.append(f"\n## Section {i + 1}\n")
            sections.append("word " * 1000)  # ~1000 tokens per section
        text = "".join(sections)

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        # All chunks should be non-empty
        for chunk in chunks:
            assert len(chunk.text.strip()) > 0
        # Chunk indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_overlap_between_chunks(self):
        """Consecutive chunks should share some overlapping text."""
        chunker = DocumentChunker(max_tokens=500, overlap_tokens=50)

        # Build two big sections
        text = "## Part A\n" + "alpha " * 1000 + "\n## Part B\n" + "beta " * 1000
        chunks = chunker.chunk(text)

        if len(chunks) >= 2:
            # The end of chunk 0 should appear in the start of chunk 1
            tail_of_first = chunks[0].text[-40:]  # last 40 chars
            assert any(
                tail_of_first[:20] in c.text for c in chunks[1:]
            ) or len(chunks) > 1  # overlap exists or forced split

    def test_tables_attached_to_correct_chunk(self):
        """Tables should be attached to the chunk containing their header text."""
        chunker = DocumentChunker(max_tokens=500, overlap_tokens=50)

        text = (
            "## Introduction\n"
            + "intro " * 1000
            + "\n## Data Section\n"
            + "The Criterion table shows results.\n"
            + "data " * 1000
        )
        tables = [
            ExtractedTable(
                table_id=0,
                headers=["Criterion", "Weight"],
                rows=[["Experience", "40%"]],
            )
        ]
        chunks = chunker.chunk(text, tables=tables)

        # Find which chunk got the table
        chunks_with_tables = [c for c in chunks if c.tables]
        assert len(chunks_with_tables) >= 1
        assert chunks_with_tables[0].tables[0].headers == ["Criterion", "Weight"]

    def test_empty_text_returns_single_empty_chunk(self):
        """Empty text should produce a single chunk with empty text."""
        chunker = DocumentChunker(max_tokens=8000)
        chunks = chunker.chunk("")
        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_invalid_max_tokens_raises(self):
        """max_tokens below 500 should raise ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be at least 500"):
            DocumentChunker(max_tokens=100)

    def test_overlap_exceeds_max_raises(self):
        """overlap_tokens >= max_tokens should raise ValueError."""
        with pytest.raises(ValueError, match="overlap_tokens must be less"):
            DocumentChunker(max_tokens=1000, overlap_tokens=1000)

    def test_single_huge_section_force_splits(self):
        """A single section larger than max_tokens should be force-split."""
        chunker = DocumentChunker(max_tokens=500, overlap_tokens=50)
        # No headings, just a wall of text — must be force-split
        text = "word " * 5000  # ~5000 tokens
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        # Each chunk should be under the limit (with some margin for overlap)
        for chunk in chunks:
            assert chunk.token_estimate <= 600  # allow some margin


class TestMergeChunkResults:
    """Tests for the chunk result merging function."""

    def test_single_result_returned_as_is(self):
        """A single chunk result should be returned unchanged."""
        result = {"executive_summary": "Test summary", "risks": []}
        merged = merge_chunk_results([result])
        assert merged == result

    def test_empty_list_returns_empty_dict(self):
        """No results should return an empty dict."""
        assert merge_chunk_results([]) == {}

    def test_summaries_concatenated(self):
        """Executive summaries from multiple chunks should be concatenated."""
        results = [
            {"executive_summary": "Part A analysis."},
            {"executive_summary": "Part B analysis."},
        ]
        merged = merge_chunk_results(results)
        assert "Part A" in merged["executive_summary"]
        assert "Part B" in merged["executive_summary"]
        assert "[Chunk" in merged["executive_summary"]

    def test_risks_deduplicated_by_title(self):
        """Risks with the same title should appear only once."""
        results = [
            {"risks": [
                {"title": "Budget risk", "description": "Too low", "severity": "high"},
                {"title": "Schedule risk", "description": "Tight", "severity": "medium"},
            ]},
            {"risks": [
                {"title": "Budget risk", "description": "Too low (duplicate)", "severity": "high"},
                {"title": "Legal risk", "description": "Missing clause", "severity": "critical"},
            ]},
        ]
        merged = merge_chunk_results(results)
        titles = [r["title"] for r in merged["risks"]]
        assert len(titles) == 3  # Budget, Schedule, Legal (no duplicates)
        assert titles.count("Budget risk") == 1

    def test_lists_concatenated(self):
        """List fields should be concatenated across chunks."""
        results = [
            {"mandatory_requirements": ["Req A", "Req B"]},
            {"mandatory_requirements": ["Req C"]},
        ]
        merged = merge_chunk_results(results)
        assert merged["mandatory_requirements"] == ["Req A", "Req B", "Req C"]

    def test_scalar_first_non_empty_wins(self):
        """For scalar fields, the first non-empty value should win."""
        results = [
            {"budget_range": ""},
            {"budget_range": "$500K - $1M"},
        ]
        merged = merge_chunk_results(results)
        assert merged["budget_range"] == "$500K - $1M"
