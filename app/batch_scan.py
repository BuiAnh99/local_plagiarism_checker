from pathlib import Path
from app.detector import HybridDetector
from app.config import DEFAULT_STORE_DIR, SUPPORTED_EXTENSIONS


def scan_folder(folder):
    # FIX: quét tất cả định dạng được hỗ trợ, không chỉ .docx
    files = [
        p for p in Path(folder).rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    # FIX: dùng DEFAULT_STORE_DIR từ config thay vì hardcode "./data"
    detector = HybridDetector(DEFAULT_STORE_DIR)

    results = {}

    for f in files:
        try:
            res = detector.check_file(f)
            results[f.name] = res
        except Exception as exc:
            results[f.name] = {"error": str(exc)}

    return results
