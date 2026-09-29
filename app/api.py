from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.detector import HybridDetector
from app.highlight import highlight_similarity
from app.extractors import extract_text as _extract_text
from functools import lru_cache
from app.config import BASE_DIR, MAX_QUERY_TEXT_CHARS, MAX_UPLOAD_BYTES, ONLINE_SEARCH_RESULTS
from app.online_evaluator import evaluate_file_online, evaluate_text_online
from app.reporting import write_check_report

app = FastAPI(title="Local Plagiarism Checker", version="1.0.0")
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates")
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _store_dir() -> Path:
    from app.config import DEFAULT_STORE_DIR
    return DEFAULT_STORE_DIR

@lru_cache(maxsize=1)
def _get_detector() -> HybridDetector:
    """Trả detector (được cache để không load model lại nhiều lần)."""
    store = _store_dir()
    if not (store / "index.db").exists():
        raise HTTPException(
            status_code=503,
            detail="Chưa có index. Hãy chạy lệnh build-index trước.",
        )
    return HybridDetector(store)

def _format_results(raw: dict, query_text: str) -> dict:
    """
    Chuyển đổi output thô của detector.check_text() sang cấu trúc template cần.

    Input (raw):
        {
            "query": "filename.txt",
            "results": [
                {"chunk_id": int, "score": float, "tfidf": float,
                 "shingle": float, "exact": float, "semantic": float,
                 "text": str, "highlights": [...]}
            ]
        }

    Output:
        {
            "query": {"filename": str, "word_count": int, "chunk_count": int},
            "matches": [ {filename, path, score_percent, risk, metrics, passages} ],
            "significant_hits": bool,
            "semantic_used": bool,
        }
    """
    if raw.get("matches") and isinstance(raw.get("query"), dict):
        return raw

    import sqlite3
    import json
    from app.config import DEFAULT_STORE_DIR
    from app.utils_text import tokens, percent, risk_label, excerpt

    chunk_rows: list[dict] = []
    doc_map: dict[int, dict] = {}

    try:
        store = DEFAULT_STORE_DIR
        with open(store / "chunk_rows.json", encoding="utf-8") as f:
            chunk_rows = json.load(f)

        conn = sqlite3.connect(store / "index.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, filename, path, word_count FROM documents").fetchall()
        doc_map = {r["id"]: dict(r) for r in rows}
        conn.close()
    except Exception as e:
        print(f"Error loading metadata: {e}")    
        pass

    # chunk_rows được index theo thứ tự id tăng dần → dùng vị trí list
    # chunk_rows[i]["doc_id"] cho biết chunk i thuộc doc nào
    chunk_index_to_row: dict[int, dict] = {r["chunk_id"]: r for r in chunk_rows}

    # Nhóm các chunk hit theo doc_id
    from collections import defaultdict
    doc_hits: dict[int, list[dict]] = defaultdict(list)

    for res in raw.get("results", []):
        cid = res["chunk_id"]
        row = chunk_index_to_row.get(cid)
        if row is None:
            continue
        doc_id = row["doc_id"]
        doc_hits[doc_id].append(res)

    SIGNIFICANT_THRESHOLD = 0.25
    matches = []

    for doc_id, hits in doc_hits.items():
        doc_info = doc_map.get(doc_id, {})
        hits_sorted = sorted(hits, key=lambda x: x["score"], reverse=True)

        top_scores = [h["score"] for h in hits_sorted[:5]]
        top_avg = sum(top_scores) / len(top_scores) if top_scores else 0.0
        best_score = top_scores[0] if top_scores else 0.0

        query_chunks_total = raw.get("_query_chunk_count", max(1, len(raw.get("results", []))))
        chunk_coverage = len(hits_sorted) / query_chunks_total

        shingle_avg = sum(h["shingle"] for h in hits_sorted[:5]) / max(1, len(hits_sorted[:5]))

        score_pct = round(best_score * 100, 1)
        risk = risk_label(score_pct)

        # Tạo passages từ top hits có highlight
        passages = []
        for h in hits_sorted[:5]:
            highlights = h.get("highlights", [])
            if highlights:
                query_exc = excerpt(highlights[0]["text"], 300) if highlights else excerpt(query_text, 300)
            else:
                query_exc = excerpt(query_text, 300)
            passages.append({
                "query_excerpt": query_exc,
                "source_excerpt": excerpt(h["text"], 300),
                "source_chunk_index": chunk_index_to_row.get(h["chunk_id"], {}).get("chunk_index", "?"),
                "score": round(h["score"] * 100, 1),
            })

        matches.append({
            "filename": doc_info.get("filename", f"doc_{doc_id}"),
            "path": doc_info.get("path", ""),
            "score_percent": score_pct,
            "risk": risk,
            "metrics": {
                "top_chunk_avg": f"{top_avg:.2f}",
                "query_chunk_coverage": f"{chunk_coverage:.1%}",
                "shingle_overlap": f"{shingle_avg:.2f}",
                "passage_coverage": f"{len(passages)} đoạn",
            },
            "passages": passages,
        })

    matches.sort(key=lambda x: x["score_percent"], reverse=True)

    word_count = len(tokens(query_text)) if query_text else 0
    query_filename = raw.get("query", "input.txt")
    if isinstance(query_filename, dict):
        query_filename = query_filename.get("filename", "input.txt")

    significant_hits = any(m["score_percent"] >= SIGNIFICANT_THRESHOLD * 100 for m in matches)

    return {
        "query": {
            "filename": query_filename,
            "word_count": word_count,
            "chunk_count": len(raw.get("results", [])),
        },
        "matches": matches,
        "significant_hits": significant_hits,
        "semantic_used": any(r.get("semantic", 0) > 0 for r in raw.get("results", [])),
    }


def _safe_overview() -> dict:
    try:
        # THAY ĐỔI: Sử dụng _get_detector() thay vì gọi trực tiếp HybridDetector
        detector = _get_detector() 
        return detector.corpus_overview()
    except Exception as exc:
        return {"meta": None, "documents": [], "error": str(exc)}


# ------------------------------------------------------------------
# HTML routes
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    overview = _safe_overview()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "overview": overview, "results": None, "text_input": ""},
    )


@app.post("/check", response_class=HTMLResponse)
async def check(
    request: Request,
    text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> HTMLResponse:

    overview = _safe_overview()

    if not overview.get("meta"):
        return templates.TemplateResponse(
            request, "index.html",
            {"request": request, "overview": overview, "results": None,
             "text_input": text, "error": "Chưa có index. Hãy chạy lệnh index trước."},
            status_code=400,
        )

    if not text.strip() and (file is None or not file.filename):
        return templates.TemplateResponse(
            request, "index.html",
            {"request": request, "overview": overview, "results": None,
             "text_input": text, "error": "Hãy dán văn bản hoặc tải lên một tệp."},
            status_code=400,
        )

    try:
        detector = _get_detector()

        if file is not None and file.filename:
            suffix = Path(file.filename).suffix or ".txt"
            content = await file.read()
            if len(content) > MAX_UPLOAD_BYTES:
                raise ValueError("File tải lên quá lớn. Hãy dùng file nhỏ hơn hoặc chia thành nhiều phần.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                query_norm = _extract_text(tmp_path)
                if len(query_norm) > MAX_QUERY_TEXT_CHARS:
                    raise ValueError("Nội dung trích xuất quá dài. Hãy chia file thành nhiều phần để kiểm tra.")
                results = detector.check_text(query_norm, filename=file.filename)
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            if len(text) > MAX_QUERY_TEXT_CHARS:
                raise ValueError("Văn bản quá dài. Hãy rút gọn hoặc chia thành nhiều lần kiểm tra.")
            results = detector.check_text(text, filename="pasted.txt")
            query_norm = text.strip()

        # Bổ sung highlight cho top kết quả
        if query_norm:
            for r in results.get("results", [])[:5]:
                r["highlights"] = highlight_similarity(query_norm, r["text"])

        # Chuyển đổi sang cấu trúc template cần
        results = _format_results(results, query_norm)

    except Exception as exc:
        return templates.TemplateResponse(
            request, "index.html",
            {"request": request, "overview": overview, "results": None,
             "text_input": text, "error": str(exc)},
            status_code=400,
        )

    return templates.TemplateResponse(
        request, "index.html",
        {"request": request, "overview": overview,
         "results": results, "text_input": text},
    )


@app.post("/batch-check-files", response_class=HTMLResponse)
async def batch_check_files(
    request: Request,
    files: list[UploadFile] = File(...),
) -> HTMLResponse:
    overview = _safe_overview()
    if not overview.get("meta"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "overview": overview,
                "results": None,
                "batch_results": None,
                "text_input": "",
                "error": "Chưa có index. Hãy chạy lệnh index trước.",
            },
            status_code=400,
        )

    detector = _get_detector()
    batch_results = []
    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix or ".txt"
        content = await upload.read()
        if len(content) > MAX_UPLOAD_BYTES:
            batch_results.append({"filename": upload.filename, "error": "File tải lên quá lớn."})
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            query_text = _extract_text(tmp_path)
            if len(query_text) > MAX_QUERY_TEXT_CHARS:
                batch_results.append({"filename": upload.filename, "error": "Nội dung trích xuất quá dài."})
                continue
            payload = detector.check_text(query_text, filename=upload.filename)
            for result in payload.get("results", [])[:5]:
                result["highlights"] = highlight_similarity(query_text, result["text"])
            report_path = write_check_report(payload)
            batch_results.append(
                {
                    "filename": upload.filename,
                    "score": payload.get("matches", [{}])[0].get("score_percent", 0) if payload.get("matches") else 0,
                    "matches": len(payload.get("matches", [])),
                    "report_name": report_path.name,
                }
            )
        except Exception as exc:
            batch_results.append({"filename": upload.filename, "error": str(exc)})
        finally:
            tmp_path.unlink(missing_ok=True)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "overview": overview,
            "results": None,
            "batch_results": batch_results,
            "text_input": "",
        },
    )


@app.get("/reports/{report_name}")
async def download_report(report_name: str) -> FileResponse:
    report_path = (BASE_DIR / "data" / "reports" / report_name).resolve()
    reports_dir = (BASE_DIR / "data" / "reports").resolve()
    if reports_dir not in report_path.parents:
        raise HTTPException(status_code=403, detail="Invalid report path.")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=report_path.name,
    )


@app.post("/evaluate-online", response_class=HTMLResponse)
async def evaluate_online(
    request: Request,
    text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    max_results: int = Form(default=ONLINE_SEARCH_RESULTS),
) -> HTMLResponse:
    overview = _safe_overview()
    if not text.strip() and (file is None or not file.filename):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "overview": overview,
                "results": None,
                "online_result": None,
                "text_input": text,
                "error": "Hãy dán văn bản hoặc tải lên một tệp để đánh giá online.",
            },
            status_code=400,
        )

    try:
        if file is not None and file.filename:
            suffix = Path(file.filename).suffix or ".txt"
            content = await file.read()
            if len(content) > MAX_UPLOAD_BYTES:
                raise ValueError("File tải lên quá lớn.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                online_result = evaluate_file_online(tmp_path, max_results=max_results)
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            if len(text) > MAX_QUERY_TEXT_CHARS:
                raise ValueError("Văn bản quá dài. Hãy rút gọn hoặc chia thành nhiều lần đánh giá.")
            online_result = evaluate_text_online(text, max_results=max_results)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "overview": overview,
                "results": None,
                "online_result": None,
                "text_input": text,
                "error": str(exc),
            },
            status_code=400,
        )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "overview": overview,
            "results": None,
            "online_result": online_result,
            "text_input": text,
        },
    )


# ------------------------------------------------------------------
# JSON API routes — dùng HybridDetector (luồng duy nhất)
# ------------------------------------------------------------------

@app.get("/api/overview")
async def api_overview() -> JSONResponse:
    return JSONResponse(_safe_overview())


@app.post("/api/check-text")
async def api_check_text(text: str = Form(...)) -> JSONResponse:
    try:
        if len(text) > MAX_QUERY_TEXT_CHARS:
            raise ValueError("Văn bản quá dài. Hãy rút gọn hoặc chia thành nhiều lần kiểm tra.")
        detector = _get_detector()
        payload  = detector.check_text(text, filename="pasted.txt")
        # Bổ sung highlight cho top 5
        for r in payload.get("results", [])[:5]:
            r["highlights"] = highlight_similarity(text, r["text"])
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/check-file")
async def api_check_file(file: UploadFile = File(...)) -> JSONResponse:
    suffix = Path(file.filename).suffix or ".txt"
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File tải lên quá lớn.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        detector = _get_detector()
        query_norm = _extract_text(tmp_path)
        if len(query_norm) > MAX_QUERY_TEXT_CHARS:
            raise HTTPException(status_code=413, detail="Nội dung trích xuất quá dài. Hãy chia file thành nhiều phần.")
        payload = detector.check_text(query_norm, filename=file.filename)
        for r in payload.get("results", [])[:5]:
            r["highlights"] = highlight_similarity(query_norm, r["text"])
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/evaluate-online-text")
async def api_evaluate_online_text(text: str = Form(...), max_results: int = Form(default=ONLINE_SEARCH_RESULTS)) -> JSONResponse:
    try:
        if len(text) > MAX_QUERY_TEXT_CHARS:
            raise ValueError("Văn bản quá dài. Hãy rút gọn hoặc chia thành nhiều lần đánh giá.")
        return JSONResponse(evaluate_text_online(text, max_results=max_results))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/evaluate-online-file")
async def api_evaluate_online_file(
    file: UploadFile = File(...),
    max_results: int = Form(default=ONLINE_SEARCH_RESULTS),
) -> JSONResponse:
    suffix = Path(file.filename).suffix or ".txt"
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File tải lên quá lớn.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        return JSONResponse(evaluate_file_online(tmp_path, max_results=max_results))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


# FIX #5: /check_text và /check_file cũ chạy qua SemanticIndexer chưa build()
# → chuyển về dùng HybridDetector cho nhất quán
@app.post("/check_text")
async def check_text_legacy(text: str = Form(...)) -> JSONResponse:
    """Legacy endpoint — giữ tương thích, chuyển về HybridDetector."""
    try:
        detector = _get_detector()
        payload  = detector.check_text(text, filename="pasted.txt")
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/check_file")
async def check_file_legacy(file: UploadFile = File(...)) -> JSONResponse:
    """Legacy endpoint — giữ tương thích, chuyển về HybridDetector."""
    suffix = Path(file.filename).suffix or ".txt"
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File tải lên quá lớn.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        detector = _get_detector()
        query_norm = _extract_text(tmp_path)
        if len(query_norm) > MAX_QUERY_TEXT_CHARS:
            raise HTTPException(status_code=413, detail="Nội dung trích xuất quá dài. Hãy chia file thành nhiều phần.")
        payload = detector.check_text(query_norm, filename=file.filename)
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/batch_scan")
def batch_scan(folder: str) -> JSONResponse:
    from app.batch_scan import scan_folder
    target = Path(folder).resolve()
    allowed_roots = [
        BASE_DIR.resolve(),
        Path(os.getenv("PLAGIARISM_CORPUS", BASE_DIR / "corpus")).resolve(),
    ]
    if not any(target == root or root in target.parents for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Chỉ được quét thư mục nằm trong dự án hoặc thư mục corpus.")
    results = scan_folder(target)
    return JSONResponse(results)


@app.get("/similarity_matrix")
def similarity_matrix() -> JSONResponse:
    from app.similarity_matrix import build_similarity_matrix

    detector = _get_detector()

    # FIX: kiểm tra embeddings trước khi tính matrix
    if detector.embeddings is None:
        raise HTTPException(
            status_code=503,
            detail="Semantic embeddings chưa được build. "
                   "Chạy lại index với --semantic-model.",
        )

    matrix = build_similarity_matrix(detector.embeddings)
    return JSONResponse({"matrix": matrix.tolist()})
