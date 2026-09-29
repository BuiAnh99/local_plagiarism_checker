from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Iterator, List, Sequence

TOKEN_RE = re.compile(r"(?u)\b\w+\b")
WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\!\?\;\:\n])\s+")


@dataclass(slots=True)
class TextChunk:
    chunk_index: int
    text: str
    start_token: int
    end_token: int


@dataclass(slots=True)
class SentenceMatch:
    query_text: str
    source_text: str
    score: float


def strip_accents(text: str) -> str:
    """Remove combining marks but keep ASCII/Unicode letters and digits."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


REPLACEMENTS = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "…": "...",
        "\u00a0": " ",
    }
)


def normalize_text(text: str, remove_accents: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(REPLACEMENTS)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if remove_accents:
        text = strip_accents(text)
    text = text.lower()
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(normalize_text(text))


def sentence_split(text: str, min_len: int = 1) -> List[str]:
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    out: List[str] = []
    for part in parts:
        if len(part) >= min_len:
            out.append(part)
    if not out and text.strip():
        return [text.strip()]
    return out


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[TextChunk]:
    token_spans = list(TOKEN_RE.finditer(text))
    if not token_spans:
        return []

    overlap = max(0, min(overlap, chunk_size - 1))
    step = max(1, chunk_size - overlap)
    result: List[TextChunk] = []
    idx = 0
    start = 0
    while start < len(token_spans):
        end = min(len(token_spans), start + chunk_size)
        start_char = token_spans[start].start()
        end_char = token_spans[end - 1].end()
        chunk_text_value = WHITESPACE_RE.sub(" ", text[start_char:end_char]).strip()
        result.append(
            TextChunk(
                chunk_index=idx,
                text=chunk_text_value,
                start_token=start,
                end_token=end,
            )
        )
        idx += 1
        if end == len(token_spans):
            break
        start += step
    return result


def build_word_shingles(text: str, size: int = 5) -> set[str]:
    toks = tokens(text)
    if not toks:
        return set()
    if len(toks) <= size:
        return {" ".join(toks)}
    return {" ".join(toks[i : i + size]) for i in range(0, len(toks) - size + 1)}


def build_char_ngrams(text: str, n: int = 4, remove_accents: bool = False) -> set[str]:
    normalized = normalize_text(text, remove_accents=remove_accents)
    if not normalized:
        return set()
    if len(normalized) <= n:
        return {normalized}
    return {normalized[i : i + n] for i in range(0, len(normalized) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def sentence_similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    seq_score = SequenceMatcher(None, a_norm, b_norm).ratio()
    char_score = jaccard(build_char_ngrams(a_norm, 4), build_char_ngrams(b_norm, 4))
    accentless_score = jaccard(
        build_char_ngrams(a_norm, 4, remove_accents=True),
        build_char_ngrams(b_norm, 4, remove_accents=True),
    )
    return 0.50 * seq_score + 0.30 * char_score + 0.20 * accentless_score


def excerpt(text: str, max_len: int = 280) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def percent(value: float) -> float:
    return round(clamp(value) * 100, 2)


def risk_label(score_percent: float) -> str:
    if score_percent >= 75:
        return "High"
    if score_percent >= 45:
        return "Medium"
    return "Low"
