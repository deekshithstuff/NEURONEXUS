from __future__ import annotations

import re
from difflib import SequenceMatcher
from unicodedata import normalize

from .preprocessing import normalize_text, tokenize


class ExactMatcher:
    """Simple exact and near-exact phrase matcher for pairwise text comparison."""

    def __init__(self, *, min_tokens: int = 4, threshold: float = 0.75, ignore_boilerplate: bool = True):
        self.min_tokens = min_tokens
        self.threshold = threshold
        self.ignore_boilerplate = ignore_boilerplate

    def match(self, source_text: str, suspicious_text: str) -> list[dict[str, object]]:
        source_tokens = self._tokens_with_offsets(source_text)
        suspicious_tokens = self._tokens_with_offsets(suspicious_text)
        if not source_tokens or not suspicious_tokens:
            return []
        if self.ignore_boilerplate and (
            normalize_text(source_text).strip(" .:;") == normalize_text(suspicious_text).strip(" .:;")
            and normalize_text(source_text).strip(" .:;") in {
                "all rights reserved",
                "table of contents",
                "conflict of interest",
                "author contributions",
                "the authors declare no competing interests",
            }
        ):
            return []

        source_words = [token for token, _, _ in source_tokens]
        suspicious_words = [token for token, _, _ in suspicious_tokens]
        if len(source_words) < self.min_tokens or len(suspicious_words) < self.min_tokens:
            return []
        matcher = SequenceMatcher(None, source_words, suspicious_words, autojunk=False)
        matches: list[dict[str, object]] = []
        for tag, source_start, source_end, suspect_start, suspect_end in matcher.get_opcodes():
            if tag != "equal":
                continue
            matched_tokens = source_words[source_start:source_end]
            if len(matched_tokens) < self.min_tokens:
                continue
            source_span = self._token_span_to_char_offsets(source_tokens, source_start, source_end)
            suspicious_span = self._token_span_to_char_offsets(suspicious_tokens, suspect_start, suspect_end)
            score = len(matched_tokens) / max(min(len(source_words), len(suspicious_words)), 1)
            if score < self.threshold:
                continue
            source_match = source_text[source_span[0] : source_span[1]]
            matches.append(
                {
                    "source_start": source_span[0],
                    "source_end": source_span[1],
                    "suspicious_start": suspicious_span[0],
                    "suspicious_end": suspicious_span[1],
                    "matched_text": source_match,
                    "score": round(score, 4),
                    "matched_tokens": len(matched_tokens),
                }
            )
        return matches

    @staticmethod
    def _tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
        found: list[tuple[str, int, int]] = []
        for match in re.finditer(r"[^\W_]+(?:['\u2019-][^\W_]+)*", text, re.UNICODE):
            token = normalize("NFKC", match.group()).casefold()
            found.append((token, match.start(), match.end()))
        return found

    @staticmethod
    def _token_span_to_char_offsets(
        tokens: list[tuple[str, int, int]], token_start: int, token_end: int
    ) -> tuple[int, int]:
        return tokens[token_start][1], tokens[token_end - 1][2]


def detect_exact_matches(source_text: str, suspicious_text: str, *, min_tokens: int = 4, threshold: float = 0.75) -> list[dict[str, object]]:
    return ExactMatcher(min_tokens=min_tokens, threshold=threshold).match(source_text, suspicious_text)
