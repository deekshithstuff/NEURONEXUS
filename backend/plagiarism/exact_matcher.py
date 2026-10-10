from __future__ import annotations

import re
from difflib import SequenceMatcher

from .preprocessing import normalize_text, tokenize


class ExactMatcher:
    """Simple exact and near-exact phrase matcher for pairwise text comparison."""

    def __init__(self, *, min_tokens: int = 4, threshold: float = 0.75, ignore_boilerplate: bool = True):
        self.min_tokens = min_tokens
        self.threshold = threshold
        self.ignore_boilerplate = ignore_boilerplate

    def match(self, source_text: str, suspicious_text: str) -> list[dict[str, object]]:
        source = normalize_text(source_text, strip_boilerplate=self.ignore_boilerplate)
        suspicious = normalize_text(suspicious_text, strip_boilerplate=self.ignore_boilerplate)
        if not source or not suspicious:
            return []

        source_tokens = tokenize(source)
        suspicious_tokens = tokenize(suspicious)
        if len(source_tokens) < self.min_tokens or len(suspicious_tokens) < self.min_tokens:
            return []

        matcher = SequenceMatcher(None, source_tokens, suspicious_tokens, autojunk=False)
        matches: list[dict[str, object]] = []
        for tag, source_start, source_end, suspect_start, suspect_end in matcher.get_opcodes():
            if tag != "equal":
                continue
            matched_tokens = source_tokens[source_start:source_end]
            if len(matched_tokens) < self.min_tokens:
                continue
            source_span = self._token_span_to_char_offsets(source, source_start, source_end)
            suspicious_span = self._token_span_to_char_offsets(suspicious, suspect_start, suspect_end)
            score = len(matched_tokens) / max(len(source_tokens), len(suspicious_tokens), 1)
            if score < self.threshold:
                continue
            matches.append(
                {
                    "source_start": source_span[0],
                    "source_end": source_span[1],
                    "suspicious_start": suspicious_span[0],
                    "suspicious_end": suspicious_span[1],
                    "matched_text": " ".join(matched_tokens),
                    "score": round(score, 4),
                    "matched_tokens": len(matched_tokens),
                }
            )
        return matches

    @staticmethod
    def _token_span_to_char_offsets(text: str, token_start: int, token_end: int) -> tuple[int, int]:
        positions = [(match.start(0), match.end(0)) for match in re.finditer(r"[A-Za-z0-9]+(?:['\u2019\-][A-Za-z0-9]+)*", text)]
        if not positions:
            return (0, len(text))
        if token_start >= len(positions):
            token_start = len(positions) - 1
        if token_end > len(positions):
            token_end = len(positions)
        start = positions[token_start][0]
        end = positions[token_end - 1][1]
        return start, end


def detect_exact_matches(source_text: str, suspicious_text: str, *, min_tokens: int = 4, threshold: float = 0.75) -> list[dict[str, object]]:
    return ExactMatcher(min_tokens=min_tokens, threshold=threshold).match(source_text, suspicious_text)
