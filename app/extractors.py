from __future__ import annotations

from pathlib import Path

from app.document_extraction import UnsupportedFileTypeError, extract_document
from app.sectioning import parse_structured_document


def extract_text(path: str | Path) -> str:
    document = extract_document(path)
    structured = parse_structured_document(document.text)
    return structured.content or document.text
