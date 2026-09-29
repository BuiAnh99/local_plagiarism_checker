from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

import joblib
import numpy as np
import scipy.sparse
from sklearn.metrics.pairwise import cosine_similarity

from app.normalizer import normalize_text
from app.shingling import jaccard_similarity, shingles
from app.utils_text import excerpt, risk_label, tokens

try:
    from sentence_transformers import SentenceTransformer

    HAS_SEMANTIC = True
except Exception:
    HAS_SEMANTIC = False


class HybridDetector:
    def __init__(self, store_dir):
        self.store_dir = Path(store_dir)
        store = self.store_dir

        self.meta = {}
        meta_path = store / "meta.json"
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as f:
                self.meta = json.load(f)

        self.word_vectorizer = joblib.load(store / "word_vectorizer.joblib")
        self.char_vectorizer = joblib.load(store / "char_vectorizer.joblib")
        self.word_matrix = scipy.sparse.load_npz(store / "word_matrix.npz")
        self.char_matrix = scipy.sparse.load_npz(store / "char_matrix.npz")

        import sqlite3

        with (store / "chunk_rows.json").open("r", encoding="utf-8") as f:
            self.rows = json.load(f)

        conn = sqlite3.connect(store / "index.db")
        cur = conn.cursor()
        cur.execute("SELECT id, text FROM chunks ORDER BY id")
        db_rows = cur.fetchall()
        self.chunk_ids = [r[0] for r in db_rows]
        self.corpus = [r[1] for r in db_rows]

        cur.execute("SELECT id, filename, path, word_count FROM documents")
        self.doc_map = {
            int(r[0]): {"filename": r[1], "path": r[2], "word_count": r[3]}
            for r in cur.fetchall()
        }
        conn.close()

        from app.config import SEMANTIC_MODEL_PATH

        self.embedder = None
        self.embeddings = None
        configured_model = SEMANTIC_MODEL_PATH or self.meta.get("semantic_model_path", "")
        if HAS_SEMANTIC and configured_model:
            try:
                self.embedder = SentenceTransformer(configured_model)
                embed_path = self.store_dir / "semantic_embeddings.npy"
                if embed_path.exists():
                    self.embeddings = np.load(embed_path)
            except Exception as exc:
                print(f"[ERROR] Failed to load semantic model or embeddings: {exc}")
                self.embedder = None
                self.embeddings = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def corpus_overview(self):
        meta_file = self.store_dir / "meta.json"
        if not meta_file.exists():
            return {"meta": None, "documents": []}

        with meta_file.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        return {
            "meta": meta,
            "documents": meta.get("documents") or list(self.doc_map.values()),
        }

    def exact_match(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    def shingle_match(self, a, b):
        return jaccard_similarity(shingles(a), shingles(b))

    def tfidf_search(self, text, top_k=20):
        v1 = self.word_vectorizer.transform([text])
        v2 = self.char_vectorizer.transform([text])
        sim_word = (v1 @ self.word_matrix.T).toarray()[0]
        sim_char = (v2 @ self.char_matrix.T).toarray()[0]
        score = 0.45 * sim_word + 0.55 * sim_char
        idx = score.argsort()[::-1][:top_k]
        return [(i, score[i]) for i in idx]

    def semantic_search(self, text, top_k=20):
        if self.embedder is None or self.embeddings is None:
            return []

        q = self.embedder.encode([text])
        scores = cosine_similarity(q, self.embeddings)[0]
        idx = scores.argsort()[::-1][:top_k]
        return [(i, scores[i]) for i in idx]

    def combine_scores(self, s_sem, s_tfidf, s_shingle):
        if self.embedder is None or self.embeddings is None:
            return 0.45 * s_tfidf + 0.55 * s_shingle
        return 0.40 * s_sem + 0.35 * s_tfidf + 0.25 * s_shingle

    def check(self, text):
        query_text = text
        text = normalize_text(text)
        tfidf_hits = dict(self.tfidf_search(text))
        semantic_hits = dict(self.semantic_search(text))
        candidate_ids = set(tfidf_hits.keys()) | set(semantic_hits.keys())

        results = []
        for i in candidate_ids:
            doc = self.corpus[i]
            doc_norm = normalize_text(doc)
            exact = self.exact_match(text, doc_norm)
            shingle = self.shingle_match(text, doc_norm)
            tfidf = tfidf_hits.get(i, 0)
            semantic = semantic_hits.get(i, 0)
            score = self.combine_scores(semantic, tfidf, shingle)
            results.append(
                {
                    "chunk_id": self.chunk_ids[i],
                    "score": float(score),
                    "exact": float(exact),
                    "shingle": float(shingle),
                    "tfidf": float(tfidf),
                    "semantic": float(semantic),
                    "text": doc[:500],
                    "query_text": query_text,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:20]

    def _format_payload(self, filename, text, results, query_chunk_count, top_docs=5):
        from collections import defaultdict

        chunk_index_to_row = {r["chunk_id"]: r for r in self.rows}
        doc_hits = defaultdict(list)
        for res in results:
            row = chunk_index_to_row.get(res["chunk_id"])
            if row is not None:
                doc_hits[row["doc_id"]].append(res)

        matches = []
        for doc_id, hits in doc_hits.items():
            doc_info = self.doc_map.get(doc_id, {})
            hits_sorted = sorted(hits, key=lambda x: x["score"], reverse=True)
            top_scores = [h["score"] for h in hits_sorted[:5]]
            top_avg = sum(top_scores) / len(top_scores) if top_scores else 0.0
            best_score = top_scores[0] if top_scores else 0.0
            chunk_coverage = len(hits_sorted) / max(1, query_chunk_count)
            shingle_avg = sum(h["shingle"] for h in hits_sorted[:5]) / max(1, len(hits_sorted[:5]))
            score_pct = round(best_score * 100, 1)

            passages = []
            for hit in hits_sorted[:5]:
                row = chunk_index_to_row.get(hit["chunk_id"], {})
                passages.append(
                    {
                        "query_excerpt": excerpt(hit.get("query_text", text), 300),
                        "source_excerpt": excerpt(hit["text"], 300),
                        "source_chunk_index": row.get("chunk_index", "?"),
                        "section_title": row.get("section_title", ""),
                        "score": round(hit["score"] * 100, 1),
                    }
                )

            matches.append(
                {
                    "filename": doc_info.get("filename", f"doc_{doc_id}"),
                    "path": doc_info.get("path", ""),
                    "score_percent": score_pct,
                    "risk": risk_label(score_pct),
                    "metrics": {
                        "top_chunk_avg": f"{top_avg:.2f}",
                        "query_chunk_coverage": f"{chunk_coverage:.1%}",
                        "shingle_overlap": f"{shingle_avg:.2f}",
                        "passage_coverage": f"{len(passages)} đoạn",
                    },
                    "section_title": hits_sorted and chunk_index_to_row.get(hits_sorted[0]["chunk_id"], {}).get("section_title", ""),
                    "passages": passages,
                }
            )

        matches.sort(key=lambda x: x["score_percent"], reverse=True)
        matches = matches[:top_docs]
        return {
            "query": {
                "filename": filename,
                "word_count": len(tokens(text)),
                "chunk_count": query_chunk_count,
            },
            "matches": matches,
            "results": results,
            "_query_chunk_count": query_chunk_count,
            "significant_hits": any(m["score_percent"] >= 25 for m in matches),
            "semantic_used": self.embedder is not None and self.embeddings is not None,
        }

    def check_text(self, text, filename="input.txt", top_docs=5):
        from app.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
        from app.sectioning import chunk_structured_document, parse_structured_document
        from app.utils_text import chunk_text

        structured = parse_structured_document(text)
        text = structured.content or text
        chunks = chunk_structured_document(structured)
        if not chunks:
            chunks = chunk_text(
                text,
                chunk_size=DEFAULT_CHUNK_SIZE,
                overlap=DEFAULT_CHUNK_OVERLAP,
            )

        if not chunks:
            results = self.check(text)
            return self._format_payload(filename, text, results, query_chunk_count=1, top_docs=top_docs)

        best_by_chunk = {}
        for chunk in chunks:
            for res in self.check(chunk.text):
                existing = best_by_chunk.get(res["chunk_id"])
                if existing is None or res["score"] > existing["score"]:
                    best_by_chunk[res["chunk_id"]] = res

        all_results = list(best_by_chunk.values())
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return self._format_payload(filename, text, all_results[:20], query_chunk_count=len(chunks), top_docs=top_docs)

    def check_file(self, file_path, top_docs=5):
        from app.extractors import extract_text

        text = extract_text(file_path)
        return self.check_text(text, filename=str(file_path), top_docs=top_docs)


PlagiarismDetector = HybridDetector
