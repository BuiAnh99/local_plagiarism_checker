from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_STORE_DIR = Path(os.getenv("PLAGIARISM_STORE", BASE_DIR / "data")).resolve()

SUPPORTED_EXTENSIONS = {".txt", ".md", ".doc", ".docx", ".pdf"}
DEFAULT_CHUNK_SIZE = 220
DEFAULT_CHUNK_OVERLAP = 70
MIN_SENTENCE_LEN = 40
MIN_CHUNK_SCORE = 0.10          # FIX: giảm từ 0.18 → 0.10 để không lọc hết kết quả khi chưa có semantic
TOP_CHUNKS_PER_QUERY = 6
TOP_DOCS = 5
MAX_PASSAGES_PER_DOC = 10
MAX_QUERY_TEXT_CHARS = 250_000
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
DEFAULT_LOCAL_EMBEDDING_MODEL = BASE_DIR / "models" / "vietnamese-sbert"
SEMANTIC_MODEL_PATH = os.getenv("SEMANTIC_MODEL_PATH", "").strip()
EMBEDDING_MODEL_PATH = os.getenv(
    "EMBEDDING_MODEL_PATH",
    SEMANTIC_MODEL_PATH or (str(DEFAULT_LOCAL_EMBEDDING_MODEL) if DEFAULT_LOCAL_EMBEDDING_MODEL.exists() else ""),
).strip()
USE_SEMANTIC = bool(SEMANTIC_MODEL_PATH)
SEMANTIC_BATCH_SIZE = int(os.getenv("SEMANTIC_BATCH_SIZE", "32"))
OPENAI_EVAL_MODEL = os.getenv("OPENAI_EVAL_MODEL", "gpt-5.5").strip()
ONLINE_SEARCH_RESULTS = int(os.getenv("ONLINE_SEARCH_RESULTS", "30"))

# Weights tuned so the system still works well for Vietnamese without a custom tokenizer.
WEIGHTS_TFIDF_ONLY = {
    "word": 0.45,
    "char": 0.55,
}
WEIGHTS_WITH_SEMANTIC = {
    "word": 0.25,
    "char": 0.35,
    "semantic": 0.40,
}
