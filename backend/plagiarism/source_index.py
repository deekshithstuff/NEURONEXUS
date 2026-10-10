from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .corpus import load_corpus
from .preprocessing import normalize_text, tokenize


@dataclass
class SourceRecord:
    source_id: str
    title: str
    text: str
    url: str | None = None
    source_type: str = "corpus"
    authors: list[str] = field(default_factory=list)
    year: str | None = None


class SourceIndex:
    """Minimal source index used to match candidate passages against known corpus entries."""

    def __init__(self, sources: list[dict[str, Any]] | None = None):
        self.sources = [self._coerce_source(source) for source in (sources or load_corpus())]
        self._inverted: dict[str, set[int]] = defaultdict(set)
        self._index = []
        self.rebuild()

    @staticmethod
    def _coerce_source(source: dict[str, Any]) -> SourceRecord:
        text = str(source.get("text") or "")
        return SourceRecord(
            source_id=str(source.get("id") or source.get("title") or "source"),
            title=str(source.get("title") or "Untitled source"),
            text=text,
            url=source.get("url"),
            source_type=str(source.get("source_type") or "corpus"),
            authors=list(source.get("authors") or []),
            year=source.get("year"),
        )

    def rebuild(self) -> None:
        self._inverted.clear()
        self._index.clear()
        for source_index, source in enumerate(self.sources):
            normalized = normalize_text(source.text)
            if not normalized:
                continue
            for sentence in normalized.split("."):
                sentence = sentence.strip()
                if not sentence:
                    continue
                tokens = tokenize(sentence)
                if len(tokens) < 2:
                    continue
                self._index.append({"source": source, "text": sentence, "tokens": tokens})
                for token in set(tokens):
                    self._inverted.setdefault(token, set()).add(len(self._index) - 1)

    def find_candidates(self, text: str, *, limit: int = 50) -> list[dict[str, Any]]:
        tokens = tokenize(text)
        if not tokens:
            return []
        matches: dict[int, int] = {}
        for token in set(tokens):
            for index in self._inverted.get(token, ()):
                matches[index] = matches.get(index, 0) + 1
        ranked = sorted(matches.items(), key=lambda item: (-item[1], item[0]))[:limit]
        results: list[dict[str, Any]] = []
        for index, overlap in ranked:
            entry = self._index[index]
            results.append({"source": entry["source"], "text": entry["text"], "overlap": overlap})
        return results

    def add_source(self, source: dict[str, Any]) -> None:
        self.sources.append(self._coerce_source(source))
        self.rebuild()

    def as_dict(self) -> list[dict[str, Any]]:
        return [{
            "id": item.source_id,
            "title": item.title,
            "text": item.text,
            "url": item.url,
            "source_type": item.source_type,
            "authors": item.authors,
            "year": item.year,
        } for item in self.sources]
