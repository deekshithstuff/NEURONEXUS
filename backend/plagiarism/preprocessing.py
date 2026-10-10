from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019\-][A-Za-z0-9]+)*")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_unicode(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or ""))


def normalize_whitespace(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", normalize_unicode(value)).strip()


def normalize_text(value: object, *, lowercase: bool = True, strip_boilerplate: bool = False) -> str:
    text = normalize_unicode(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    if lowercase:
        text = text.lower()
    text = text.strip()
    if strip_boilerplate:
        text = _strip_common_boilerplate(text)
    return text


def _strip_common_boilerplate(value: str) -> str:
    cleaned = value
    for phrase in (
        "all rights reserved",
        "table of contents",
        "conflict of interest",
        "author contributions",
        "the authors declare no competing interests",
    ):
        if cleaned.lower().startswith(phrase):
            cleaned = cleaned[len(phrase) :].lstrip(" -:;,.\n")
            break
    return cleaned.strip()


def tokenize(value: object) -> list[str]:
    text = normalize_unicode(value)
    return [match.group(0).lower() for match in _WORD_RE.finditer(text)]


def sentence_split(value: object) -> list[str]:
    text = normalize_unicode(value)
    if not text.strip():
        return []
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"\u2018\u201c])", text)
    return [segment.strip() for segment in chunks if segment.strip()]


def split_sentences(value: object) -> list[str]:
    return sentence_split(value)


def ngrams(items: Iterable[str], n: int) -> list[str]:
    window = list(items)
    if n <= 0 or not window:
        return []
    return [" ".join(window[index : index + n]) for index in range(len(window) - n + 1)]


def split_passages(text: object, *, max_chars: int = 400, overlap: int = 80) -> list[str]:
    value = normalize_unicode(text or "")
    if not value.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(value):
        end = min(len(value), start + max_chars)
        segment = value[start:end].strip()
        if segment:
            chunks.append(segment)
        if end >= len(value):
            break
        start += max(1, max_chars - overlap)
    return chunks


def remove_short_tokens(tokens: Iterable[str], min_length: int = 2) -> list[str]:
    return [token for token in tokens if len(token) >= min_length]
