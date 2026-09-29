from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.detector import PlagiarismDetector
from app.indexer import build_index

CORPUS = ROOT / "examples" / "corpus"
STORE = ROOT / "tests" / ".tmp_store"


def test_index_and_check() -> None:
    summary = build_index(CORPUS, STORE, rebuild=True)
    assert summary["documents_indexed"] >= 3

    query = (
        "Trí tuệ nhân tạo được dùng ngày càng nhiều trong giáo dục đại học. "
        "Các hệ thống hỗ trợ học tập có thể gợi ý tài liệu và phản hồi lỗi phổ biến "
        "trong bài làm của sinh viên."
    )

    with PlagiarismDetector(STORE) as detector:
        result = detector.check_text(query, filename="query.txt", top_docs=3)

    assert result["matches"], "Expected at least one match"
    top = result["matches"][0]
    assert top["filename"] == "bai_goc_01.txt"
    assert top["score_percent"] > 40
