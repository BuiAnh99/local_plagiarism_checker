from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
from scipy import sparse

INDEX_DB_NAME = "index.db"
META_NAME = "meta.json"
WORD_VECTORIZER_NAME = "word_vectorizer.joblib"
CHAR_VECTORIZER_NAME = "char_vectorizer.joblib"
WORD_MATRIX_NAME = "word_matrix.npz"
CHAR_MATRIX_NAME = "char_matrix.npz"
CHUNK_ROWS_NAME = "chunk_rows.json"
SEMANTIC_EMBEDDINGS_NAME = "semantic_embeddings.npy"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    section_key TEXT NOT NULL DEFAULT '',
    section_title TEXT NOT NULL DEFAULT '',
    paragraph_index INTEGER NOT NULL DEFAULT 0,
    heading_path TEXT NOT NULL DEFAULT '[]',
    extractor TEXT NOT NULL DEFAULT '',
    ocr_used INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks(chunk_index);
"""


def ensure_store(store_dir: str | Path) -> Path:
    store_path = Path(store_dir).resolve()
    store_path.mkdir(parents=True, exist_ok=True)
    return store_path



def db_path(store_dir: str | Path) -> Path:
    return ensure_store(store_dir) / INDEX_DB_NAME



def connect_db(store_dir: str | Path) -> sqlite3.Connection:
    path = db_path(store_dir)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()



def clear_store(store_dir: str | Path) -> None:
    store_path = ensure_store(store_dir)
    for child in store_path.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        else:
            shutil.rmtree(child)



def insert_document(conn: sqlite3.Connection, path: str, filename: str, sha256: str, text: str, word_count: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO documents(path, filename, sha256, text, word_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (path, filename, sha256, text, word_count),
    )
    return int(cur.lastrowid)



def insert_chunk(
    conn: sqlite3.Connection,
    doc_id: int,
    chunk_index: int,
    start_token: int,
    end_token: int,
    text: str,
    token_count: int,
    section_key: str = "",
    section_title: str = "",
    paragraph_index: int = 0,
    heading_path: Sequence[str] | None = None,
    extractor: str = "",
    ocr_used: bool = False,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO chunks(
            doc_id, chunk_index, start_token, end_token, text, token_count,
            section_key, section_title, paragraph_index, heading_path, extractor, ocr_used
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            chunk_index,
            start_token,
            end_token,
            text,
            token_count,
            section_key,
            section_title,
            paragraph_index,
            json.dumps(list(heading_path or []), ensure_ascii=False),
            extractor,
            int(ocr_used),
        ),
    )
    return int(cur.lastrowid)



def fetch_document(conn: sqlite3.Connection, doc_id: int) -> dict:
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else {}



def fetch_documents(conn: sqlite3.Connection, doc_ids: Sequence[int]) -> dict[int, dict]:
    if not doc_ids:
        return {}
    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(f"SELECT * FROM documents WHERE id IN ({placeholders})", tuple(doc_ids)).fetchall()
    return {int(row["id"]): dict(row) for row in rows}



def fetch_chunks_by_ids(conn: sqlite3.Connection, chunk_ids: Sequence[int]) -> dict[int, dict]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = conn.execute(f"SELECT * FROM chunks WHERE id IN ({placeholders})", tuple(chunk_ids)).fetchall()
    return {int(row["id"]): dict(row) for row in rows}



def list_documents(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, path, filename, sha256, word_count FROM documents ORDER BY filename ASC").fetchall()
    return [dict(row) for row in rows]



def save_json(store_dir: str | Path, filename: str, payload: dict | list) -> Path:
    path = ensure_store(store_dir) / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path



def load_json(store_dir: str | Path, filename: str) -> dict | list:
    path = ensure_store(store_dir) / filename
    return json.loads(path.read_text(encoding="utf-8"))



def save_meta(store_dir: str | Path, payload: dict) -> Path:
    return save_json(store_dir, META_NAME, payload)



def load_meta(store_dir: str | Path) -> dict:
    return load_json(store_dir, META_NAME)  # type: ignore[return-value]



def save_chunk_rows(store_dir: str | Path, rows: list[dict]) -> Path:
    return save_json(store_dir, CHUNK_ROWS_NAME, rows)



def load_chunk_rows(store_dir: str | Path) -> list[dict]:
    return load_json(store_dir, CHUNK_ROWS_NAME)  # type: ignore[return-value]



def save_joblib(store_dir: str | Path, filename: str, obj: object) -> Path:
    path = ensure_store(store_dir) / filename
    joblib.dump(obj, path)
    return path



def load_joblib(store_dir: str | Path, filename: str) -> object:
    path = ensure_store(store_dir) / filename
    return joblib.load(path)



def save_sparse_matrix(store_dir: str | Path, filename: str, matrix: sparse.spmatrix) -> Path:
    path = ensure_store(store_dir) / filename
    sparse.save_npz(path, matrix)
    return path



def load_sparse_matrix(store_dir: str | Path, filename: str) -> sparse.spmatrix:
    path = ensure_store(store_dir) / filename
    return sparse.load_npz(path)



def save_semantic_embeddings(store_dir: str | Path, embeddings: np.ndarray) -> Path:
    path = ensure_store(store_dir) / SEMANTIC_EMBEDDINGS_NAME
    np.save(path, embeddings)
    return path



def load_semantic_embeddings(store_dir: str | Path) -> np.ndarray:
    path = ensure_store(store_dir) / SEMANTIC_EMBEDDINGS_NAME
    return np.load(path)
