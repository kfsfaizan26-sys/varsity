from __future__ import annotations

import logging

import fitz

from app.models.extracted_document import ExtractedDocument

logger = logging.getLogger(__name__)


def _table_to_text(rows: list[list]) -> str:
    """Convert table rows to pipe-separated lines (preserves columns for Gemini)."""
    lines: list[str] = []
    for row in rows:
        cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_tables_from_page(page: fitz.Page, page_index: int) -> list[str]:
    table_parts: list[str] = []
    try:
        finder = page.find_tables()
        tables = getattr(finder, "tables", None) or []
        for table_index, table in enumerate(tables):
            try:
                rows = table.extract()
                if rows:
                    body = _table_to_text(rows)
                    table_parts.append(
                        f"--- page {page_index + 1} table {table_index + 1} ---\n{body}"
                    )
            except Exception as exc:
                logger.debug("Table extract failed page %s: %s", page_index + 1, exc)
    except Exception as exc:
        logger.debug("find_tables failed page %s: %s", page_index + 1, exc)
    return table_parts


def extract_pdf_text(data: bytes) -> ExtractedDocument:
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        text_parts: list[str] = []
        table_parts: list[str] = []
        warnings: list[str] = []

        for i in range(len(doc)):
            page = doc[i]
            table_parts.extend(_extract_tables_from_page(page, i))

            # sort=True improves reading order for multi-column / table layouts
            page_text = page.get_text("text", sort=True).strip()
            if page_text:
                text_parts.append(f"--- page {i + 1} ---\n{page_text}")

        tables_markdown = "\n\n".join(table_parts)
        full_text = "\n\n".join(text_parts)

        # Prefer structured tables for AI when present (typical for student lists)
        if tables_markdown and not full_text.strip():
            full_text = tables_markdown
        elif tables_markdown:
            full_text = f"{tables_markdown}\n\n--- additional page text ---\n\n{full_text}"

        if not full_text.strip():
            warnings.append("No text extracted from PDF pages")

        if tables_markdown:
            warnings.append(f"Extracted {len(table_parts)} table(s) from PDF")

        return ExtractedDocument(
            full_text=full_text,
            detected_type="pdf_text",
            page_count=len(doc),
            tables_markdown=tables_markdown or None,
            warnings=warnings,
        )
    finally:
        doc.close()
