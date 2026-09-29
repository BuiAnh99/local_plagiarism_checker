from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz
from docx import Document

from app.config import SUPPORTED_EXTENSIONS
from app.utils_text import WHITESPACE_RE


class UnsupportedFileTypeError(ValueError):
    pass


@dataclass(slots=True)
class ExtractedDocument:
    text: str
    markdown: str = ""
    extractor: str = ""
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)
    quality: dict = field(default_factory=dict)


TEXT_ENCODINGS = ["utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"]
MIN_USABLE_TEXT_CHARS = 120
MIN_OCR_TRIGGER_CHARS = 40
MIN_ALPHA_NUM_RATIO = 0.25


def extract_document(path: str | Path, ocr: str = "auto") -> ExtractedDocument:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")

    if suffix in {".txt", ".md"}:
        text = _extract_plain_text(file_path)
        return _with_quality(ExtractedDocument(text=text, markdown=text, extractor="plain_text"))
    if suffix in {".doc", ".docx"}:
        return _extract_docx_document(file_path)
    if suffix == ".pdf":
        return _extract_pdf_document(file_path, ocr=ocr)

    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")


def _extract_plain_text(path: Path) -> str:
    last_error: UnicodeDecodeError | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return ""


def _extract_docx_document(path: Path) -> ExtractedDocument:
    warnings: list[str] = []
    markitdown_text = _try_markitdown(path, warnings)
    if _has_usable_text(markitdown_text):
        return _with_quality(ExtractedDocument(text=markitdown_text, markdown=markitdown_text, extractor="markitdown", warnings=warnings))

    if path.suffix.lower() == ".doc":
        return _with_quality(ExtractedDocument(text=markitdown_text, markdown=markitdown_text, extractor="markitdown", warnings=warnings))

    text = _extract_docx(path)
    return _with_quality(ExtractedDocument(text=text, markdown=text, extractor="python-docx", warnings=warnings))


def _extract_pdf_document(path: Path, ocr: str = "auto") -> ExtractedDocument:
    warnings: list[str] = []
    markdown = _try_pymupdf4llm(path, warnings)
    if _has_usable_text(markdown):
        return _with_quality(ExtractedDocument(text=markdown, markdown=markdown, extractor="pymupdf4llm", warnings=warnings))

    markitdown_text = _try_markitdown(path, warnings)
    if _has_usable_text(markitdown_text):
        return _with_quality(ExtractedDocument(text=markitdown_text, markdown=markitdown_text, extractor="markitdown", warnings=warnings))

    fitz_text = _extract_pdf_with_fitz(path)
    if _has_usable_text(fitz_text) and ocr != "always":
        return _with_quality(ExtractedDocument(text=fitz_text, markdown=fitz_text, extractor="pymupdf", warnings=warnings))

    best_text = _best_text(markdown, markitdown_text, fitz_text)
    if ocr == "always" or (ocr == "auto" and _should_ocr(best_text)):
        ocr_text = _try_ocr_pdf(path, warnings)
        if ocr_text.strip():
            return _with_quality(
                ExtractedDocument(
                    text=ocr_text,
                    markdown=ocr_text,
                    extractor="pytesseract",
                    ocr_used=True,
                    warnings=warnings,
                )
            )

    if best_text == markdown:
        extractor = "pymupdf4llm"
    elif best_text == markitdown_text:
        extractor = "markitdown"
    else:
        extractor = "pymupdf"
    warnings.append("OCR skipped because extractor returned some text; text may be short or low quality.")
    return _with_quality(ExtractedDocument(text=best_text, markdown=best_text, extractor=extractor, warnings=warnings))


def _try_pymupdf4llm(path: Path, warnings: list[str]) -> str:
    try:
        import pymupdf4llm  # type: ignore

        return pymupdf4llm.to_markdown(str(path)) or ""
    except Exception as exc:
        warnings.append(f"pymupdf4llm unavailable: {exc}")
        return ""


def _try_markitdown(path: Path, warnings: list[str]) -> str:
    try:
        from markitdown import MarkItDown  # type: ignore

        result = MarkItDown().convert(str(path))
        return getattr(result, "text_content", "") or ""
    except Exception as exc:
        warnings.append(f"markitdown unavailable: {exc}")
        return ""


def _try_ocr_pdf(path: Path, warnings: list[str]) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # noqa: F401
    except Exception as exc:
        warnings.append(f"pytesseract unavailable: {exc}")
        return ""

    parts: list[str] = []
    try:
        with fitz.open(path) as pdf:
            for page in pdf:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(image, lang="vie+eng")
                if text.strip():
                    parts.append(text)
    except Exception as exc:
        warnings.append(f"ocr failed: {exc}")
    return "\n\n".join(parts)


def _extract_docx(path: Path) -> str:
    doc = Document(str(path))
    parts: list[str] = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def _extract_pdf_with_fitz(path: Path) -> str:
    parts: list[str] = []
    with fitz.open(path) as pdf:
        for page in pdf:
            text = page.get_text("text")
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts)


def _with_quality(document: ExtractedDocument) -> ExtractedDocument:
    document.text = _cleanup_text(document.text)
    document.markdown = _cleanup_text(document.markdown or document.text)
    document.quality = _quality_score(document.text)
    return document


def _cleanup_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return text.strip()


def _quality_score(text: str) -> dict:
    stripped = text.strip()
    alpha_num = sum(ch.isalnum() for ch in stripped)
    ratio = alpha_num / max(1, len(stripped))
    paragraphs = len([p for p in stripped.splitlines() if p.strip()])
    return {
        "chars": len(stripped),
        "alpha_num_ratio": round(ratio, 3),
        "paragraphs": paragraphs,
        "usable": _has_usable_text(stripped),
        "ocr_candidate": _should_ocr(stripped),
    }


def _has_usable_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    alpha_num = sum(ch.isalnum() for ch in stripped)
    ratio = alpha_num / max(1, len(stripped))
    return len(stripped) >= MIN_USABLE_TEXT_CHARS and ratio >= MIN_ALPHA_NUM_RATIO


def _should_ocr(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    alpha_num = sum(ch.isalnum() for ch in stripped)
    ratio = alpha_num / max(1, len(stripped))
    return len(stripped) < MIN_OCR_TRIGGER_CHARS or ratio < 0.15


def _best_text(*values: str) -> str:
    return max(values, key=lambda value: (sum(ch.isalnum() for ch in value), len(value)), default="")
