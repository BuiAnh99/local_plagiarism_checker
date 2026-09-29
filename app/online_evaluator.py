from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import EMBEDDING_MODEL_PATH, ONLINE_SEARCH_RESULTS, OPENAI_EVAL_MODEL, SEMANTIC_BATCH_SIZE
from app.document_extraction import extract_document
from app.semantic import load_semantic_backend
from app.sectioning import StructuredDocument, parse_structured_document
from app.utils_text import WHITESPACE_RE, excerpt


RUBRIC_SCHEMA = {
    "name": "innovation_online_evaluation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "online_scan": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "queries": {"type": "array", "items": {"type": "string"}},
                    "results_found": {"type": "integer"},
                    "results_reviewed": {"type": "integer"},
                    "similar_sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "snippet_or_excerpt": {"type": "string"},
                                "similarity_reason": {"type": "string"},
                                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                            },
                            "required": ["title", "url", "snippet_or_excerpt", "similarity_reason", "risk_level"],
                        },
                    },
                },
                "required": ["queries", "results_found", "results_reviewed", "similar_sources"],
            },
            "rubric": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "novelty_creativity": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": "integer"},
                            "max_score": {"type": "integer"},
                            "reason": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["score", "max_score", "reason", "evidence", "risks"],
                    },
                    "effectiveness_benefits": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": "integer"},
                            "max_score": {"type": "integer"},
                            "reason": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["score", "max_score", "reason", "evidence", "risks"],
                    },
                    "scalability": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": "integer"},
                            "max_score": {"type": "integer"},
                            "reason": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["score", "max_score", "reason", "evidence", "risks"],
                    },
                    "total_score": {"type": "integer"},
                },
                "required": ["novelty_creativity", "effectiveness_benefits", "scalability", "total_score"],
            },
            "final_comment": {"type": "string"},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["title", "online_scan", "rubric", "final_comment", "confidence"],
    },
    "strict": True,
}


def evaluate_file_online(path: str | Path, max_results: int = ONLINE_SEARCH_RESULTS) -> dict[str, Any]:
    extracted = extract_document(path)
    structured = parse_structured_document(extracted.text)
    return evaluate_structured_online(structured, max_results=max_results, extraction={
        "extractor": extracted.extractor,
        "ocr_used": extracted.ocr_used,
        "warnings": extracted.warnings,
        "quality": extracted.quality,
    })


def evaluate_text_online(text: str, max_results: int = ONLINE_SEARCH_RESULTS) -> dict[str, Any]:
    structured = parse_structured_document(text)
    return evaluate_structured_online(structured, max_results=max_results, extraction={})


def evaluate_structured_online(
    structured: StructuredDocument,
    max_results: int = ONLINE_SEARCH_RESULTS,
    extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "status": "blocked",
            "error": "Chưa cấu hình OPENAI_API_KEY nên không thể quét online.",
            "structured": _structured_summary(structured),
        }

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        return {
            "status": "blocked",
            "error": f"Chưa cài thư viện openai: {exc}",
            "structured": _structured_summary(structured),
        }

    max_results = max(20, min(30, int(max_results or ONLINE_SEARCH_RESULTS)))
    queries = build_search_queries(structured, max_results=max_results)
    prompt = _build_prompt(structured, queries, max_results)
    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=OPENAI_EVAL_MODEL,
        input=prompt,
        tools=[{"type": "web_search_preview", "search_context_size": "high"}],
        text={"format": {"type": "json_schema", **RUBRIC_SCHEMA}},
    )

    payload = _parse_response_json(response)
    payload["status"] = "ready"
    payload["model"] = OPENAI_EVAL_MODEL
    payload["structured"] = _structured_summary(structured)
    payload["extraction"] = extraction or {}
    payload["embedding_comparison"] = _compare_online_findings(structured, payload)
    return payload


def build_search_queries(structured: StructuredDocument, max_results: int = ONLINE_SEARCH_RESULTS) -> list[str]:
    title = structured.title or _guess_title(structured.content)
    field_value = structured.field
    keywords = _keywords(title)
    query_parts = [
        f'"{title}"' if title else "",
        f'"{title}" "sáng kiến kinh nghiệm"' if title else "",
        f'"{title}" "bản mô tả sáng kiến"' if title else "",
        f'"{title}" filetype:pdf' if title else "",
    ]
    if keywords:
        query_parts.extend(
            [
                f'"{keywords}" "sáng kiến kinh nghiệm"',
                f'"{keywords}" "bản mô tả sáng kiến"',
                f'"{keywords}" "giải pháp"',
            ]
        )
    if field_value and keywords:
        query_parts.append(f'"{keywords}" "{field_value}"')
    return [q for q in query_parts if q][:8]


def _build_prompt(structured: StructuredDocument, queries: list[str], max_results: int) -> str:
    sections = {key: {"title": section.title, "text": excerpt(section.text, 3500)} for key, section in structured.sections.items()}
    data = {
        "title": structured.title or _guess_title(structured.content),
        "field": structured.field,
        "section_start_found": structured.section_start_found,
        "sections": sections,
        "fallback_content_excerpt": excerpt(structured.content, 5000),
        "queries": queries,
        "max_results": max_results,
    }
    return (
        "Bạn là hội đồng thẩm định sáng kiến. Hãy dùng công cụ web search để quét online chủ động theo các truy vấn, "
        f"ưu tiên đọc và đối chiếu {max_results} kết quả đầu tiên tìm được từ tên sáng kiến và từ khóa liên quan. "
        "Không chỉ tìm trùng tên; hãy tìm cả nguồn có giải pháp, cấu trúc triển khai hoặc đoạn mô tả tương tự. "
        "Sau đó chấm theo rubric: Tính mới, tính sáng tạo 30 điểm; Hiệu quả áp dụng, lợi ích thu được 40 điểm; "
        "Khả năng nhân rộng 30 điểm. Chỉ trả JSON theo schema.\n\n"
        f"Dữ liệu sáng kiến:\n{json.dumps(data, ensure_ascii=False)}"
    )


def _parse_response_json(response: Any) -> dict[str, Any]:
    text = getattr(response, "output_text", "") or ""
    if not text:
        chunks: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                value = getattr(content, "text", None)
                if value:
                    chunks.append(value)
        text = "\n".join(chunks)
    return json.loads(text)


def _compare_online_findings(structured: StructuredDocument, payload: dict[str, Any]) -> dict[str, Any]:
    section_texts = [section.text for section in structured.sections.values() if section.text.strip()]
    if not section_texts:
        section_texts = [structured.content]

    findings = payload.get("online_scan", {}).get("similar_sources", [])
    online_texts = [
        WHITESPACE_RE.sub(" ", f"{f.get('title', '')} {f.get('snippet_or_excerpt', '')} {f.get('similarity_reason', '')}").strip()
        for f in findings
    ]
    online_texts = [text for text in online_texts if text]
    if not online_texts:
        return {
            "method": "semantic_embedding" if EMBEDDING_MODEL_PATH else "tfidf_cosine",
            "online_sources_compared": 0,
            "max_similarity": 0.0,
            "top_matches": [],
        }

    semantic_result = _compare_with_semantic_embeddings(section_texts, online_texts, findings)
    if semantic_result is not None:
        return semantic_result

    return _compare_with_tfidf(section_texts, online_texts, findings)


def _compare_with_semantic_embeddings(
    section_texts: list[str],
    online_texts: list[str],
    findings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not EMBEDDING_MODEL_PATH:
        return None

    backend = load_semantic_backend(EMBEDDING_MODEL_PATH, batch_size=SEMANTIC_BATCH_SIZE)
    if backend is None:
        return None

    try:
        section_matrix = backend.encode(section_texts)
        online_matrix = backend.encode(online_texts)
    except Exception:
        return None

    sims = cosine_similarity(section_matrix, online_matrix)
    top_matches = _top_online_matches(sims, findings)
    return {
        "method": "semantic_embedding_cosine",
        "model_path": EMBEDDING_MODEL_PATH,
        "online_sources_compared": len(online_texts),
        "max_similarity": top_matches[0]["similarity"] if top_matches else 0.0,
        "top_matches": top_matches[:10],
    }


def _compare_with_tfidf(
    section_texts: list[str],
    online_texts: list[str],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    corpus = section_texts + online_texts
    vectorizer = TfidfVectorizer(analyzer="word", ngram_range=(1, 3), token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform(corpus)
    section_matrix = matrix[: len(section_texts)]
    online_matrix = matrix[len(section_texts) :]
    sims = cosine_similarity(section_matrix, online_matrix)
    top_matches = _top_online_matches(sims, findings)
    return {
        "method": "tfidf_cosine_over_online_excerpts",
        "online_sources_compared": len(online_texts),
        "max_similarity": top_matches[0]["similarity"] if top_matches else 0.0,
        "top_matches": top_matches[:10],
    }


def _top_online_matches(sims: Any, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top_matches = []
    for online_idx, finding in enumerate(findings):
        score = float(sims[:, online_idx].max()) if online_idx < sims.shape[1] else 0.0
        top_matches.append(
            {
                "title": finding.get("title", ""),
                "url": finding.get("url", ""),
                "similarity": round(score, 4),
            }
        )
    top_matches.sort(key=lambda item: item["similarity"], reverse=True)
    return top_matches


def _structured_summary(structured: StructuredDocument) -> dict[str, Any]:
    return {
        "title": structured.title or _guess_title(structured.content),
        "field": structured.field,
        "section_start_found": structured.section_start_found,
        "sections": {
            key: {"title": section.title, "word_count": len(section.text.split())}
            for key, section in structured.sections.items()
        },
    }


def _guess_title(text: str) -> str:
    lines = [line.strip(" .:-\t") for line in text.splitlines() if line.strip(" .:-\t")]
    for line in lines:
        if 8 <= len(line) <= 180 and "sáng kiến" not in line.lower() and not re.match(r"^(mẫu|ban|bản)\b", line.lower()):
            return line
    return ""


def _keywords(title: str) -> str:
    title = WHITESPACE_RE.sub(" ", title).strip()
    title = re.sub(r"(?i)\b(một số|biện pháp|giải pháp|nâng cao|hiệu quả|ứng dụng)\b", " ", title)
    title = WHITESPACE_RE.sub(" ", title).strip()
    words = title.split()
    if len(words) > 12:
        words = words[:12]
    return " ".join(words)
