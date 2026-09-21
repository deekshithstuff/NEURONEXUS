from __future__ import annotations

<<<<<<< HEAD
import re

from .rules import get_available_journals, get_journal_rules


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _token_set(texts: list[str] | str | None) -> set[str]:
    if texts is None:
        return set()
    if isinstance(texts, str):
        parts = [texts]
    else:
        parts = texts
    tokens: set[str] = set()
    for part in parts:
        for token in _normalize_token(part).split():
            if token:
                tokens.add(token)
    return tokens


def match_journal(document_metadata: dict) -> dict:
    if not isinstance(document_metadata, dict):
        return get_journal_rules("nature")

    title = document_metadata.get("title") or ""
    abstract = document_metadata.get("abstract") or ""
    keywords = document_metadata.get("keywords") or []
    sections = document_metadata.get("sections") or []
    section_text = " ".join((section.get("content") or section.get("heading") or "") for section in sections if isinstance(section, dict))
    manuscript_text = " ".join([title, abstract, section_text, *[str(keyword) for keyword in keywords]])
    manuscript_tokens = _token_set(manuscript_text)

    best_journal = get_journal_rules("nature")
    best_score = -1.0

    for journal in get_available_journals():
        scope_tokens = _token_set(journal.get("scope_topics") or [])
        if not scope_tokens:
            continue
        overlap = manuscript_tokens & scope_tokens
        if not manuscript_tokens:
            overlap_score = 0.0
        else:
            overlap_score = len(overlap) / len(manuscript_tokens)
        if len(scope_tokens):
            coverage = len(overlap) / len(scope_tokens)
        else:
            coverage = 0.0
        score = round(min(0.99, (overlap_score * 0.7) + (coverage * 0.3)), 4)
        if score > best_score:
            best_score = score
            best_journal = journal

    return best_journal
=======
from .rules import get_available_journals, get_journal_rules


def match_journal(document_metadata: dict) -> dict:
    title = (document_metadata.get("title") or "").lower()
    for journal in get_available_journals():
        if "ieee" in title and journal["journal_id"] == "ieee":
            return journal
        if "nature" in title and journal["journal_id"] == "nature":
            return journal
    return get_journal_rules("nature")
>>>>>>> 7824d8913e2157f6ebc06f3a0d20be405780bfa0
