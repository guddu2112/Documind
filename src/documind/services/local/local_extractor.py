"""Local document extractor — offline replacement for
``DocumentIntelligenceService``.

Uses:
    - PyMuPDF (``pymupdf``)  for PDFs (text + tables when available)
    - python-docx            for .docx
    - openpyxl               for .xlsx
    - plain read             for .txt / .md

Returns a small dataclass, ``LocalAnalysisResult``, whose attributes
match the subset of the Azure Document Intelligence result that the
current extractor tools expect (``content``, ``pages``,
``key_value_pairs``, ``tables``).

Public interface mirrors ``DocumentIntelligenceService`` exactly:
    - analyze_document(file_bytes, model_id) -> LocalAnalysisResult
    - extract_text, extract_key_value_pairs, extract_tables, get_page_count
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

from documind.core.models.base import ExtractedTable, KeyValuePair

logger = logging.getLogger(__name__)


# ── Duck-typed replacements for the DI SDK result objects ────────


@dataclass
class LocalPage:
    page_number: int


@dataclass
class LocalTable:
    """Duck-types azure.ai.documentintelligence.models.DocumentTable."""

    row_count: int
    column_count: int
    cells: list[Any] = field(default_factory=list)
    bounding_regions: list[dict[str, Any]] | None = None


@dataclass
class LocalTableCell:
    row_index: int
    column_index: int
    content: str


@dataclass
class LocalAnalysisResult:
    """Duck-types the subset of DI's AnalyzeResult that we consume."""

    content: str = ""
    pages: list[LocalPage] = field(default_factory=list)
    tables: list[LocalTable] = field(default_factory=list)
    key_value_pairs: list[Any] = field(default_factory=list)


# ── Format detection ────────────────────────────────────────────


def _sniff_format(file_bytes: bytes) -> str:
    """Guess the format from magic bytes. Returns ``pdf``/``docx``/``xlsx``/``text``/``unknown``."""
    if len(file_bytes) >= 4 and file_bytes[:4] == b"%PDF":
        return "pdf"
    if len(file_bytes) >= 4 and file_bytes[:4] == b"PK\x03\x04":
        # ZIP container — could be docx, xlsx, pptx. Peek inside.
        try:
            import zipfile

            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" in names:
                    return "docx"
                if "xl/workbook.xml" in names:
                    return "xlsx"
                if "ppt/presentation.xml" in names:
                    return "pptx"
        except Exception:
            return "unknown"
        return "unknown"
    try:
        file_bytes[: min(len(file_bytes), 2048)].decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        return "unknown"


# ── Individual parsers ─────────────────────────────────────────


def _parse_pdf(file_bytes: bytes) -> LocalAnalysisResult:
    import pymupdf  # noqa: F401  — imported lazily

    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        pages: list[LocalPage] = []
        tables: list[LocalTable] = []
        parts: list[str] = []
        for i, page in enumerate(doc, start=1):
            pages.append(LocalPage(page_number=i))
            parts.append(page.get_text("text") or "")
            # PyMuPDF ≥1.23 exposes a table finder
            try:
                found = page.find_tables()
                for t in found:
                    grid = t.extract() or []
                    cells: list[LocalTableCell] = []
                    row_count = len(grid)
                    col_count = max((len(r) for r in grid), default=0)
                    for r_idx, row in enumerate(grid):
                        for c_idx, cell in enumerate(row):
                            cells.append(
                                LocalTableCell(
                                    row_index=r_idx,
                                    column_index=c_idx,
                                    content=str(cell) if cell is not None else "",
                                )
                            )
                    tables.append(
                        LocalTable(
                            row_count=row_count,
                            column_count=col_count,
                            cells=cells,
                            bounding_regions=[{"page_number": i}],
                        )
                    )
            except Exception as exc:
                logger.debug("PyMuPDF table detection failed on page %d: %s", i, exc)

        content = "\n".join(p.strip() for p in parts if p and p.strip())
        return LocalAnalysisResult(content=content, pages=pages, tables=tables)


def _parse_docx(file_bytes: bytes) -> LocalAnalysisResult:
    import docx

    document = docx.Document(io.BytesIO(file_bytes))
    text_parts: list[str] = [p.text for p in document.paragraphs if p.text]
    tables: list[LocalTable] = []
    for tbl in document.tables:
        cells: list[LocalTableCell] = []
        row_count = len(tbl.rows)
        col_count = max((len(r.cells) for r in tbl.rows), default=0)
        for r_idx, row in enumerate(tbl.rows):
            for c_idx, cell in enumerate(row.cells):
                cells.append(
                    LocalTableCell(
                        row_index=r_idx,
                        column_index=c_idx,
                        content=cell.text or "",
                    )
                )
        tables.append(LocalTable(row_count=row_count, column_count=col_count, cells=cells))
    # docx has no explicit "pages" concept without rendering; use one logical page.
    return LocalAnalysisResult(
        content="\n".join(text_parts),
        pages=[LocalPage(page_number=1)],
        tables=tables,
    )


def _parse_xlsx(file_bytes: bytes) -> LocalAnalysisResult:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    pages: list[LocalPage] = []
    tables: list[LocalTable] = []
    text_parts: list[str] = []
    for sheet_idx, ws in enumerate(wb.worksheets, start=1):
        pages.append(LocalPage(page_number=sheet_idx))
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        row_count = len(rows)
        col_count = max((len(r) for r in rows), default=0)
        cells: list[LocalTableCell] = []
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                cells.append(
                    LocalTableCell(
                        row_index=r_idx,
                        column_index=c_idx,
                        content="" if val is None else str(val),
                    )
                )
        tables.append(
            LocalTable(
                row_count=row_count,
                column_count=col_count,
                cells=cells,
                bounding_regions=[{"page_number": sheet_idx}],
            )
        )
        text_parts.append(
            "\n".join(
                "\t".join("" if v is None else str(v) for v in row)
                for row in rows
            )
        )
    wb.close()
    return LocalAnalysisResult(content="\n\n".join(text_parts), pages=pages, tables=tables)


def _parse_text(file_bytes: bytes) -> LocalAnalysisResult:
    text = file_bytes.decode("utf-8", errors="replace")
    return LocalAnalysisResult(content=text, pages=[LocalPage(page_number=1)])


# ── Service ────────────────────────────────────────────────────


class LocalExtractor:
    """DocumentIntelligenceService-compatible local extractor."""

    def analyze_document(
        self,
        file_bytes: bytes,
        model_id: str = "prebuilt-layout",
    ) -> LocalAnalysisResult:
        fmt = _sniff_format(file_bytes)
        logger.info("LocalExtractor detected format=%s (model_id=%s ignored)", fmt, model_id)
        if fmt == "pdf":
            return _parse_pdf(file_bytes)
        if fmt == "docx":
            return _parse_docx(file_bytes)
        if fmt == "xlsx":
            return _parse_xlsx(file_bytes)
        if fmt == "text":
            return _parse_text(file_bytes)
        logger.warning("LocalExtractor: unsupported format (%s) — returning empty result", fmt)
        return LocalAnalysisResult()

    def extract_text(self, analysis_result: LocalAnalysisResult) -> str:
        return getattr(analysis_result, "content", "") or ""

    def extract_key_value_pairs(
        self, analysis_result: LocalAnalysisResult
    ) -> list[KeyValuePair]:
        # No native KV extraction offline; return an empty list so downstream
        # code (which is defensive about empty KV) still works.
        return []

    def extract_tables(self, analysis_result: LocalAnalysisResult) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        for idx, table in enumerate(getattr(analysis_result, "tables", []) or []):
            row_count = table.row_count or 0
            col_count = table.column_count or 0
            grid = [["" for _ in range(col_count)] for _ in range(row_count)]
            for cell in (table.cells or []):
                r, c = cell.row_index, cell.column_index
                if 0 <= r < row_count and 0 <= c < col_count:
                    grid[r][c] = cell.content or ""
            headers = grid[0] if grid else []
            rows = grid[1:] if len(grid) > 1 else []
            page = None
            if table.bounding_regions:
                page = table.bounding_regions[0].get("page_number")
            tables.append(
                ExtractedTable(
                    table_id=idx,
                    headers=headers,
                    rows=rows,
                    page=page,
                )
            )
        return tables

    def get_page_count(self, analysis_result: LocalAnalysisResult) -> int:
        return len(getattr(analysis_result, "pages", []) or [])
