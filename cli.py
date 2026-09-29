from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.detector import HybridDetector
from app.indexer import build_index



def default_store_dir() -> str:
    return str(Path(os.getenv("PLAGIARISM_STORE", "./data")).resolve())



def print_payload(payload: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"Input: {payload['query']['filename']} | {payload['query']['word_count']} words | {payload['query']['chunk_count']} chunks")
    if payload.get("semantic_used"):
        print("Semantic model: enabled")
    elif payload.get("semantic_warning"):
        print(f"Semantic warning: {payload['semantic_warning']}")
    print()
    for idx, match in enumerate(payload["matches"], start=1):
        print(f"[{idx}] {match['filename']}")
        print(f"    Score: {match['score_percent']}% ({match['risk']})")
        print(f"    Path : {match['path']}")
        print(
            "    Metrics: "
            f"top_chunk_avg={match['metrics']['top_chunk_avg']}, "
            f"coverage={match['metrics']['query_chunk_coverage']}, "
            f"shingle={match['metrics']['shingle_overlap']}, "
            f"passage={match['metrics']['passage_coverage']}"
        )
        for passage in match["passages"][:3]:
            print(f"    - Passage {passage['score']}%")
            print(f"      Query : {passage['query_excerpt']}")
            print(f"      Source: {passage['source_excerpt']}")
        print()



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local plagiarism checker for Vietnamese and mixed-language corpora.")
    sub = parser.add_subparsers(dest="command", required=True)

    index_cmd = sub.add_parser("index", help="Build or rebuild the local index from a corpus directory.")
    index_cmd.add_argument("--corpus", required=True, help="Directory containing TXT/MD/DOCX/PDF files.")
    index_cmd.add_argument("--store", default=default_store_dir(), help="Directory to store the index.")
    index_cmd.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    index_cmd.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    index_cmd.add_argument("--rebuild", action="store_true", help="Clear the store and rebuild the whole corpus.")
    index_cmd.add_argument(
        "--semantic-model-path",
        default="",
        help="Optional local path to a sentence-transformer model. No online download is performed.",
    )

    check_file_cmd = sub.add_parser("check-file", help="Check a file against the local corpus.")
    check_file_cmd.add_argument("--file", required=True)
    check_file_cmd.add_argument("--store", default=default_store_dir())
    check_file_cmd.add_argument("--top", type=int, default=5)
    check_file_cmd.add_argument("--json", action="store_true")

    check_text_cmd = sub.add_parser("check-text", help="Check raw text against the local corpus.")
    check_text_cmd.add_argument("--text", help="Text to check.")
    check_text_cmd.add_argument("--text-file", help="Plain text file to read input text from.")
    check_text_cmd.add_argument("--stdin", action="store_true", help="Read input text from STDIN.")
    check_text_cmd.add_argument("--store", default=default_store_dir())
    check_text_cmd.add_argument("--top", type=int, default=5)
    check_text_cmd.add_argument("--json", action="store_true")

    serve_cmd = sub.add_parser("serve", help="Run the local web UI.")
    serve_cmd.add_argument("--store", default=default_store_dir())
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--reload", action="store_true")

    return parser



def read_text_from_args(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.stdin:
        return sys.stdin.read()
    raise SystemExit("Provide --text, --text-file, or --stdin.")



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "index":
        summary = build_index(
            corpus_dir=args.corpus,
            store_dir=args.store,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            semantic_model_path=args.semantic_model_path,
            rebuild=args.rebuild,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "check-file":
        with HybridDetector(args.store) as detector:
            payload = detector.check_file(args.file, top_docs=args.top)
        print_payload(payload, as_json=args.json)
        return

    if args.command == "check-text":
        text = read_text_from_args(args)
        with HybridDetector(args.store) as detector:
            payload = detector.check_text(text, filename="input.txt", top_docs=args.top)
        print_payload(payload, as_json=args.json)
        return

    if args.command == "serve":
        os.environ["PLAGIARISM_STORE"] = str(Path(args.store).resolve())
        import uvicorn

        uvicorn.run("app.api:app", host=args.host, port=args.port, reload=args.reload)
        return


if __name__ == "__main__":
    main()
