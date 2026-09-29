from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from app.config import DEFAULT_STORE_DIR


def safe_report_name(filename: str) -> str:
    stem = Path(filename).stem or "report"
    stem = re.sub(r"[^\w\-. ]+", "_", stem, flags=re.UNICODE).strip(" ._")
    return f"{stem or 'report'}_ket_qua.docx"


def write_check_report(payload: dict, output_dir: str | Path | None = None) -> Path:
    report_dir = Path(output_dir or (DEFAULT_STORE_DIR / "reports")).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    query = payload.get("query", {})
    filename = query.get("filename", "report")
    path = report_dir / safe_report_name(filename)

    doc = Document()
    doc.add_heading("Báo cáo đối chiếu sáng kiến", level=1)
    doc.add_paragraph(f"Tài liệu kiểm tra: {filename}")
    doc.add_paragraph(f"Số từ: {query.get('word_count', 0)}")
    doc.add_paragraph(f"Số chunk kiểm tra: {query.get('chunk_count', 0)}")
    doc.add_paragraph(f"Sử dụng semantic: {'Có' if payload.get('semantic_used') else 'Không'}")

    matches = payload.get("matches", [])
    if not matches:
        doc.add_heading("Kết quả", level=2)
        doc.add_paragraph("Không tìm thấy nguồn tương đồng rõ ràng trong corpus.")
        doc.save(path)
        return path

    doc.add_heading("Nguồn tương đồng", level=2)
    for idx, match in enumerate(matches, start=1):
        doc.add_heading(f"{idx}. {match.get('filename', '')}", level=3)
        doc.add_paragraph(f"Điểm: {match.get('score_percent', 0)}% - {match.get('risk', '')}")
        if match.get("path"):
            doc.add_paragraph(f"Đường dẫn nguồn: {match.get('path')}")
        metrics = match.get("metrics", {})
        doc.add_paragraph(
            "Chỉ số: "
            f"top_chunk_avg={metrics.get('top_chunk_avg', '')}; "
            f"coverage={metrics.get('query_chunk_coverage', '')}; "
            f"shingle={metrics.get('shingle_overlap', '')}; "
            f"passage={metrics.get('passage_coverage', '')}"
        )

        for passage_idx, passage in enumerate(match.get("passages", [])[:5], start=1):
            doc.add_paragraph(f"Đoạn {passage_idx} - {passage.get('score', 0)}%")
            if passage.get("section_title"):
                doc.add_paragraph(f"Mục nguồn: {passage.get('section_title')}")
            doc.add_paragraph("Văn bản kiểm tra:")
            doc.add_paragraph(passage.get("query_excerpt", ""))
            doc.add_paragraph("Nguồn trong corpus:")
            doc.add_paragraph(passage.get("source_excerpt", ""))

    doc.save(path)
    return path
