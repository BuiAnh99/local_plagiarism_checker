from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field as dc_field

from app.utils_text import TOKEN_RE, WHITESPACE_RE


START_PATTERNS = [
    "ban mo ta sang kien",
    "ban mo ta sang kien kinh nghiem",
    "mo ta sang kien",
]

COMPARISON_SECTION_KEYS = {
    "proposed_solution",
    "novelty",
    "scalability",
    "effectiveness",
}

COMPARISON_START_PATTERNS = [
    "iii noi dung giai phap de nghi cong nhan sang kien",
    "iii 1 noi dung giai phap de nghi cong nhan sang kien",
    "iii noi dung giai phap",
    "iii 1 noi dung giai phap",
]


SECTION_PATTERNS = [
    ("title", r"(?im)^\s*(?:1[\.\)]\s*)?t[eê]n\s+s[aá]ng\s+ki[eế]n\s*[:\-\.]*\s*(.*)$"),
    ("field", r"(?im)^\s*(?:2[\.\)]\s*)?l[iĩ]nh\s+v[uự]c\s+[aá]p\s+d[uụ]ng\s+s[aá]ng\s+ki[eế]n\s*[:\-\.]*\s*(.*)$"),
    ("known_solution", r"(?im)^\s*II[\.\)]\s*m[oô]\s+t[aả]\s+gi[aả]i\s+ph[aá]p\s+[dđ][aã]\s+bi[eế]t\b"),
    ("proposed_solution", r"(?im)^\s*III(?:[\.\s]*1)?[\.\)]\s*n[oộ]i\s+dung\s+gi[aả]i\s+ph[aá]p\b"),
    ("novelty", r"(?im)^\s*III[\.\s]*2[\.\)]\s*t[ií]nh\s+m[oớ]i\b"),
    ("scalability", r"(?im)^\s*III[\.\s]*3[\.\)]\s*ph[aạ]m\s+vi\s+[aả]nh\s+h[uư][oở]ng\b"),
    ("effectiveness", r"(?im)^\s*III[\.\s]*4[\.\)]\s*hi[eệ]u\s+qu[aả]\b"),
]


HEADING_RE = re.compile(
    r"(?im)^\s*((?:[IVX]{1,5}|[0-9]+(?:\.[0-9]+)*|[a-z])[\.\)]\s+.{3,160}|(?:BẢN|BAN)\s+MÔ\s+TẢ\s+SÁNG\s+KIẾN.*)$"
)


@dataclass(slots=True)
class StructuredSection:
    key: str
    title: str
    text: str


@dataclass(slots=True)
class StructuredDocument:
    title: str = ""
    field: str = ""
    content: str = ""
    section_start_found: bool = False
    sections: dict[str, StructuredSection] = dc_field(default_factory=dict)


@dataclass(slots=True)
class SectionChunk:
    chunk_index: int
    text: str
    start_token: int
    end_token: int
    section_key: str
    section_title: str
    paragraph_index: int
    heading_path: list[str]


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def loose_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def trim_to_innovation_description(text: str) -> tuple[str, bool]:
    norm = loose_normalize(text)
    best_norm_pos: int | None = None
    for pattern in START_PATTERNS:
        pos = norm.find(pattern)
        if pos >= 0 and (best_norm_pos is None or pos < best_norm_pos):
            best_norm_pos = pos

    if best_norm_pos is None:
        return text.strip(), False

    raw_pos = _approximate_raw_position(text, norm, best_norm_pos)
    return text[raw_pos:].strip(), True


def trim_to_comparison_content(text: str) -> tuple[str, bool]:
    norm = loose_normalize(text)
    best_norm_pos: int | None = None
    for pattern in COMPARISON_START_PATTERNS:
        pos = norm.find(pattern)
        if pos >= 0 and (best_norm_pos is None or pos < best_norm_pos):
            best_norm_pos = pos

    if best_norm_pos is None:
        return text.strip(), False

    raw_pos = _approximate_raw_position(text, norm, best_norm_pos)
    return text[raw_pos:].strip(), True


def _approximate_raw_position(raw: str, normalized: str, normalized_pos: int) -> int:
    if normalized_pos <= 0:
        return 0

    seen = 0
    last_space = True
    for idx, ch in enumerate(raw):
        n = loose_normalize(ch)
        if not n:
            if not last_space:
                seen += 1
                last_space = True
            continue
        if not last_space:
            seen += 1
        seen += len(n)
        last_space = False
        if seen >= normalized_pos:
            return idx
    return 0


def parse_structured_document(text: str) -> StructuredDocument:
    content, found = trim_to_innovation_description(text)
    sections = _extract_named_sections(content)
    title = _extract_inline_field(content, "title")
    field_value = _extract_inline_field(content, "field")
    return StructuredDocument(
        title=title,
        field=field_value,
        content=content,
        section_start_found=found,
        sections=sections,
    )


def _extract_inline_field(text: str, key: str) -> str:
    needle = "ten sang kien" if key == "title" else "linh vuc ap dung sang kien"
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if needle not in loose_normalize(line):
            continue
        value = line.split(":", 1)[1] if ":" in line else ""
        value = value.strip(" .:-\t")
        if value and not set(value) <= {"."}:
            return WHITESPACE_RE.sub(" ", value).strip()
        for next_line in lines[idx + 1 : idx + 4]:
            cleaned = next_line.strip(" .:-\t")
            if cleaned and not set(cleaned) <= {"."}:
                return WHITESPACE_RE.sub(" ", cleaned).strip()
    return ""


def _extract_named_sections(text: str) -> dict[str, StructuredSection]:
    marker_specs = [
        ("known_solution", ["ii mo ta giai phap da biet", "ii mo ta giai phap"]),
        ("proposed_solution", ["iii 1 noi dung giai phap", "iii noi dung giai phap de nghi"]),
        ("novelty", ["iii 2 tinh moi", "iii2 tinh moi"]),
        ("scalability", ["iii 3 pham vi anh huong", "iii3 pham vi anh huong"]),
        ("effectiveness", ["iii 4 hieu qua", "iii4 hieu qua"]),
    ]
    markers: list[tuple[int, str, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        norm = loose_normalize(line)
        for key, needles in marker_specs:
            if any(needle in norm for needle in needles):
                markers.append((pos, key, WHITESPACE_RE.sub(" ", line).strip()))
                break
        pos += len(line)

    markers.sort(key=lambda x: x[0])
    sections: dict[str, StructuredSection] = {}
    for idx, (start, key, title) in enumerate(markers):
        end = markers[idx + 1][0] if idx + 1 < len(markers) else len(text)
        section_text = text[start:end].strip()
        sections[key] = StructuredSection(key=key, title=title, text=section_text)
    return sections


def chunk_structured_document(doc: StructuredDocument, min_words: int = 45, max_words: int = 260) -> list[SectionChunk]:
    source_sections = {
        key: section
        for key, section in doc.sections.items()
        if key in COMPARISON_SECTION_KEYS
    }
    if not source_sections:
        comparison_text, found_comparison_start = trim_to_comparison_content(doc.content)
        if not found_comparison_start:
            return []
        source_sections = {
            "comparison_body": StructuredSection(
                "comparison_body",
                "III. Nội dung giải pháp đề nghị công nhận sáng kiến",
                comparison_text,
            )
        }
    chunks: list[SectionChunk] = []
    global_token = 0

    for section in source_sections.values():
        paragraphs = _paragraphs_with_heading_context(section.text)
        paragraph_index = 0
        buffer: list[str] = []
        buffer_heading: list[str] = [section.title]
        buffer_start = global_token

        for paragraph, heading_path in paragraphs:
            words = TOKEN_RE.findall(paragraph)
            if not words:
                continue
            if not buffer:
                buffer_start = global_token
                buffer_heading = heading_path or [section.title]
            buffer.append(paragraph)
            global_token += len(words)

            if sum(len(TOKEN_RE.findall(p)) for p in buffer) >= min_words:
                paragraph_index = _flush_buffer(
                    chunks,
                    buffer,
                    section,
                    buffer_heading,
                    buffer_start,
                    paragraph_index,
                    max_words,
                )
                buffer = []

        if buffer:
            _flush_buffer(chunks, buffer, section, buffer_heading, buffer_start, paragraph_index, max_words)

    return chunks


def _paragraphs_with_heading_context(text: str) -> list[tuple[str, list[str]]]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    heading_path: list[str] = []
    out: list[tuple[str, list[str]]] = []

    for block in blocks:
        first_line = block.splitlines()[0].strip()
        if HEADING_RE.match(first_line):
            heading_path = [first_line]
            rest = "\n".join(block.splitlines()[1:]).strip()
            if rest:
                out.append((rest, heading_path.copy()))
            continue
        out.append((block, heading_path.copy()))
    return out


def _flush_buffer(
    chunks: list[SectionChunk],
    buffer: list[str],
    section: StructuredSection,
    heading_path: list[str],
    start_token: int,
    paragraph_index: int,
    max_words: int,
) -> int:
    text = WHITESPACE_RE.sub(" ", "\n\n".join(buffer)).strip()
    words = TOKEN_RE.findall(text)
    if len(words) <= max_words:
        chunks.append(
            SectionChunk(
                chunk_index=len(chunks),
                text=text,
                start_token=start_token,
                end_token=start_token + len(words),
                section_key=section.key,
                section_title=section.title,
                paragraph_index=paragraph_index,
                heading_path=heading_path,
            )
        )
        return paragraph_index + 1

    step = max_words
    for start in range(0, len(words), step):
        part_words = words[start : start + max_words]
        if not part_words:
            continue
        chunks.append(
            SectionChunk(
                chunk_index=len(chunks),
                text=" ".join(part_words),
                start_token=start_token + start,
                end_token=start_token + start + len(part_words),
                section_key=section.key,
                section_title=section.title,
                paragraph_index=paragraph_index,
                heading_path=heading_path,
            )
        )
        paragraph_index += 1
    return paragraph_index
