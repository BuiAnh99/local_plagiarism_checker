from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer

from .config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, EMBEDDING_MODEL_PATH, SEMANTIC_BATCH_SIZE
from .document_extraction import extract_document
from .extractors import UnsupportedFileTypeError, extract_text
from .semantic import load_semantic_backend
from .sectioning import chunk_structured_document, parse_structured_document
from .storage import (
    CHAR_MATRIX_NAME,
    CHAR_VECTORIZER_NAME,
    WORD_MATRIX_NAME,
    WORD_VECTORIZER_NAME,
    clear_store,
    connect_db,
    init_db,
    insert_chunk,
    insert_document,
    save_chunk_rows,
    save_joblib,
    save_meta,
    save_semantic_embeddings,
    save_sparse_matrix,
)
from .utils_text import chunk_text, tokens


SUPPORTED_SKIP_REASONS = {
    "empty": "Document is empty after text extraction.",
    "unsupported": "Unsupported file type.",
    "extract_error": "Unable to extract text.",
}



def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()



def iter_supported_files(corpus_dir: str | Path) -> list[Path]:
    root = Path(corpus_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Corpus directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Corpus path is not a directory: {root}")
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md", ".doc", ".docx", ".pdf"}])



def build_index(
    corpus_dir: str | Path,
    store_dir: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    semantic_model_path: str = "",
    rebuild: bool = False,
) -> dict:
    corpus_path = Path(corpus_dir).resolve()
    semantic_model_path = semantic_model_path or EMBEDDING_MODEL_PATH
    if rebuild:
        clear_store(store_dir)

    conn = connect_db(store_dir)
    init_db(conn)
    migrate_db(conn)

    files = iter_supported_files(corpus_path)
    if not files:
        raise FileNotFoundError(f"No supported files found in corpus directory: {corpus_path}")

    skipped: list[dict] = []
    documents_added = 0
    documents_skipped_existing = 0
    existing_paths = set()
    if not rebuild:
        existing_rows = conn.execute("SELECT path FROM documents").fetchall()
        existing_paths = {str(row["path"]) for row in existing_rows}

    for file_path in files:
        file_path_str = str(file_path)
        if file_path_str in existing_paths:
            documents_skipped_existing += 1
            continue

        try:
            extracted = extract_document(file_path)
            structured = parse_structured_document(extracted.text)
            text = structured.content or extracted.text
        except UnsupportedFileTypeError:
            skipped.append({"path": str(file_path), "reason": SUPPORTED_SKIP_REASONS["unsupported"]})
            continue
        except Exception as exc:  # pragma: no cover - best effort extraction logging
            skipped.append({"path": str(file_path), "reason": f"{SUPPORTED_SKIP_REASONS['extract_error']} {exc}"})
            continue

        word_list = tokens(text)
        if not word_list:
            skipped.append({"path": str(file_path), "reason": SUPPORTED_SKIP_REASONS["empty"]})
            continue

        doc_id = insert_document(
            conn,
            path=file_path_str,
            filename=file_path.name,
            sha256=file_sha256(file_path),
            text=text,
            word_count=len(word_list),
        )
        documents_added += 1

        chunks = chunk_structured_document(structured)
        if not chunks:
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for chunk in chunks:
            section_key = getattr(chunk, "section_key", "")
            section_title = getattr(chunk, "section_title", "")
            paragraph_index = getattr(chunk, "paragraph_index", 0)
            heading_path = getattr(chunk, "heading_path", [])
            chunk_id = insert_chunk(
                conn,
                doc_id=doc_id,
                chunk_index=chunk.chunk_index,
                start_token=chunk.start_token,
                end_token=chunk.end_token,
                text=chunk.text,
                token_count=chunk.end_token - chunk.start_token,
                section_key=section_key,
                section_title=section_title,
                paragraph_index=paragraph_index,
                heading_path=heading_path,
                extractor=extracted.extractor,
                ocr_used=extracted.ocr_used,
            )
    conn.commit()

    all_chunk_texts, all_chunk_rows = load_all_index_chunks(conn)
    documents_total = conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]
    conn.close()

    if not all_chunk_texts:
        raise RuntimeError("No chunks were created. Check that the corpus contains readable text documents.")

    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 3),
        token_pattern=r"(?u)\b\w+\b",
        lowercase=False,
        sublinear_tf=True,
        norm="l2",
        min_df=1,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=False,
        sublinear_tf=True,
        norm="l2",
        min_df=1,
    )

    word_matrix = word_vectorizer.fit_transform(all_chunk_texts)
    char_matrix = char_vectorizer.fit_transform(all_chunk_texts)

    save_joblib(store_dir, WORD_VECTORIZER_NAME, word_vectorizer)
    save_joblib(store_dir, CHAR_VECTORIZER_NAME, char_vectorizer)
    save_sparse_matrix(store_dir, WORD_MATRIX_NAME, word_matrix)
    save_sparse_matrix(store_dir, CHAR_MATRIX_NAME, char_matrix)
    save_chunk_rows(store_dir, all_chunk_rows)

    semantic_enabled = False
    if semantic_model_path:
        backend = load_semantic_backend(semantic_model_path, batch_size=SEMANTIC_BATCH_SIZE)
        if backend is not None:
            embeddings = backend.encode(all_chunk_texts)
            save_semantic_embeddings(store_dir, embeddings)
            semantic_enabled = True

    summary = {
        "corpus_dir": str(corpus_path),
        "store_dir": str(Path(store_dir).resolve()),
        "documents_indexed": documents_total,
        "documents_added": documents_added,
        "documents_skipped_existing": documents_skipped_existing,
        "chunks_indexed": len(all_chunk_rows),
        "index_mode": "rebuild" if rebuild else "incremental_new_files_only",
        "chunking_strategy": "structured_sections_with_paragraphs_fallback_token_chunks",
        "structured_chunks_indexed": sum(1 for row in all_chunk_rows if row.get("section_key")),
        "fallback_chunks_indexed": sum(1 for row in all_chunk_rows if not row.get("section_key")),
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "semantic_enabled": semantic_enabled,
        "semantic_model_path": semantic_model_path or "",
        "skipped": skipped,
    }
    save_meta(store_dir, summary)
    return summary


def migrate_db(conn) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(chunks)").fetchall()}
    columns = {
        "section_key": "TEXT NOT NULL DEFAULT ''",
        "section_title": "TEXT NOT NULL DEFAULT ''",
        "paragraph_index": "INTEGER NOT NULL DEFAULT 0",
        "heading_path": "TEXT NOT NULL DEFAULT '[]'",
        "extractor": "TEXT NOT NULL DEFAULT ''",
        "ocr_used": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE chunks ADD COLUMN {name} {definition}")
    conn.commit()


def load_all_index_chunks(conn) -> tuple[list[str], list[dict]]:
    rows = conn.execute(
        """
        SELECT
            c.id AS chunk_id,
            c.doc_id,
            d.filename AS doc_filename,
            c.chunk_index,
            c.start_token,
            c.end_token,
            c.text,
            c.token_count,
            c.section_key,
            c.section_title,
            c.paragraph_index,
            c.heading_path,
            c.extractor,
            c.ocr_used
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        ORDER BY c.id
        """
    ).fetchall()
    chunk_texts: list[str] = []
    chunk_rows: list[dict] = []
    for row in rows:
        chunk_texts.append(row["text"])
        try:
            heading_path = json.loads(row["heading_path"] or "[]")
        except json.JSONDecodeError:
            heading_path = []
        chunk_rows.append(
            {
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "doc_filename": row["doc_filename"],
                "chunk_index": row["chunk_index"],
                "start_token": row["start_token"],
                "end_token": row["end_token"],
                "token_count": row["token_count"],
                "section_key": row["section_key"] or "",
                "section_title": row["section_title"] or "",
                "paragraph_index": row["paragraph_index"] or 0,
                "heading_path": heading_path,
                "extractor": row["extractor"] or "",
                "ocr_used": bool(row["ocr_used"]),
            }
        )
    return chunk_texts, chunk_rows
