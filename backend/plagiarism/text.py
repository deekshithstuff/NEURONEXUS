"""Text normalization helpers shared by the plagiarism engines.

These utilities keep sentence and character offsets intact so every reported
match can be traced back to an exact location in the manuscript.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019\-][A-Za-z0-9]+)*")
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"\u201c'])")
_DOUBLE_QUOTE_RE = re.compile(r"[\"\u201c]([^\"\u201d]{2,}?)[\"\u201d]")
_CITATION_RE = re.compile(
    r"\[(\d+(?:\s*[-,]\s*\d+)*)\]"
    r"|\b[A-Z][A-Za-z-]+(?:\s+et al\.)?\s*\(\s*\d{4}[a-z]?\s*\)"
)


def normalize_whitespace(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def tokenize(value: object) -> list[str]:
    return [word.lower() for word in _WORD_RE.findall(str(value or ""))]


def word_count(value: object) -> int:
    return len(_WORD_RE.findall(str(value or "")))


def split_sentences(text: object) -> list[tuple[str, int, int]]:
    """Split text into sentences, returning (sentence, start, end) offsets."""
    value = str(text or "")
    if not value.strip():
        return []
    sentences: list[tuple[str, int, int]] = []
    cursor = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(value):
        _append_sentence(sentences, value, cursor, match.start())
        cursor = match.end()
    _append_sentence(sentences, value, cursor, len(value))
    return sentences


def _append_sentence(sentences: list[tuple[str, int, int]], value: str, start: int, end: int) -> None:
    segment = value[start:end]
    stripped = segment.strip()
    if not stripped:
        return
    leading = len(segment) - len(segment.lstrip())
    real_start = start + leading
    sentences.append((stripped, real_start, real_start + len(stripped)))


def quotation_spans(text: object) -> list[tuple[int, int]]:
    """Return character spans of text enclosed in double quotation marks."""
    value = str(text or "")
    return [(match.start(1), match.end(1)) for match in _DOUBLE_QUOTE_RE.finditer(value)]


def has_citation(text: object) -> bool:
    return bool(_CITATION_RE.search(str(text or "")))


def span_within(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(span_start <= start and end <= span_end for span_start, span_end in spans)


def is_fully_quoted(text: object) -> bool:
    value = str(text or "").strip()
    return len(value) >= 2 and value[0] in "\"\u201c" and value[-1] in "\"\u201d"
