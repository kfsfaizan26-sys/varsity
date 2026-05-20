from __future__ import annotations

import io

import pandas as pd

from app.models.extracted_document import ExtractedDocument


def _dataframe_to_markdown(frame: pd.DataFrame) -> str:
    cols = [str(c) for c in frame.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = [
        "| " + " | ".join(str(row[c]) for c in frame.columns) + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, sep, *rows])


def extract_excel(data: bytes) -> ExtractedDocument:
    buffer = io.BytesIO(data)
    sheets: dict[str, pd.DataFrame] = pd.read_excel(buffer, sheet_name=None, engine="openpyxl")
    md_parts: list[str] = []
    text_parts: list[str] = []
    for name, frame in sheets.items():
        frame = frame.fillna("")
        md = _dataframe_to_markdown(frame)
        md_parts.append(f"## Sheet: {name}\n\n{md}")
        text_parts.append(f"--- sheet: {name} ---\n{frame.to_string(index=False)}")
    return ExtractedDocument(
        full_text="\n\n".join(text_parts),
        detected_type="excel",
        page_count=len(sheets),
        tables_markdown="\n\n".join(md_parts),
        warnings=[] if text_parts else ["Excel file contained no readable sheets"],
    )
