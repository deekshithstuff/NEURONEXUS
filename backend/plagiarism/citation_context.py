from __future__ import annotations

import re

CITATION_PATTERNS = [
    re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]"),
    re.compile(r"\b[A-Z][A-Za-z-]+(?:\s+et al\.)?\s*\(\s*\d{4}[a-z]?\s*\)"),
]


def citation_context(text: str) -> list[str]:
    value = text or ""
    contexts: list[str] = []
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(value):
            start = max(0, match.start() - 80)
            end = min(len(value), match.end() + 80)
            contexts.append(value[start:end].strip())
    return contexts


def has_citation_context(text: str) -> bool:
    return bool(citation_context(text))


def citation_aware_score(text: str, *, base_score: float = 0.0) -> float:
    if has_citation_context(text):
        return base_score + 0.1
    return base_score
