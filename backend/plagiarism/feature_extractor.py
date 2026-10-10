from __future__ import annotations

from typing import Any

from .citation_context import citation_aware_score, has_citation_context
from .exact_matcher import ExactMatcher
from .lexical_matcher import lexical_similarity_features
from .preprocessing import normalize_text, tokenize
from .semantic_matcher import semantic_similarity


class FeatureExtractor:
    def __init__(self, *, use_semantic: bool = True):
        self.use_semantic = use_semantic
        self.exact_matcher = ExactMatcher(min_tokens=3, threshold=0.6)

    def extract(self, source_text: str, suspicious_text: str, *, citation_context_text: str | None = None) -> dict[str, Any]:
        source = normalize_text(source_text)
        suspicious = normalize_text(suspicious_text)
        lexical = lexical_similarity_features(source, suspicious)
        exact_matches = self.exact_matcher.match(source, suspicious)
        exact_phrase_match = 1.0 if exact_matches else 0.0
        semantic_score = semantic_similarity(source, suspicious) if self.use_semantic else 0.0
        source_tokens = tokenize(source)
        suspicious_tokens = tokenize(suspicious)
        overlap_ratio = 0.0 if not source_tokens or not suspicious_tokens else len(set(source_tokens) & set(suspicious_tokens)) / max(len(set(source_tokens) | set(suspicious_tokens)), 1)
        length_ratio = 0.0 if not source_tokens or not suspicious_tokens else min(len(source_tokens), len(suspicious_tokens)) / max(len(source_tokens), len(suspicious_tokens), 1)
        citation_indicator = int(bool(has_citation_context(citation_context_text or "")))

        vector = {
            "exact_phrase_match": float(exact_phrase_match),
            "word_overlap": float(lexical["word_overlap"]),
            "char_overlap": float(lexical["char_overlap"]),
            "tfidf_cosine": float(lexical["tfidf_cosine"]),
            "semantic_cosine": float(semantic_score),
            "distinctive_phrase_ratio": float(lexical["distinctive_phrase_ratio"]),
            "passage_length_ratio": float(length_ratio),
            "citation_context_indicator": citation_indicator,
            "shared_token_ratio": float(overlap_ratio),
            "citation_context_score": citation_aware_score(citation_context_text or "", base_score=0.0),
        }
        return vector


def extract_features(source_text: str, suspicious_text: str, *, citation_context_text: str | None = None, use_semantic: bool = True) -> dict[str, Any]:
    return FeatureExtractor(use_semantic=use_semantic).extract(source_text, suspicious_text, citation_context_text=citation_context_text)


def extract_feature_matrix(rows: list[dict[str, Any]], *, use_semantic: bool = True) -> list[dict[str, Any]]:
    feature_rows: list[dict[str, Any]] = []
    for row in rows:
        source_text = str(row.get("source_text") or "")
        suspicious_text = str(row.get("suspicious_text") or "")
        citation_context_text = row.get("citation_context")
        feature_rows.append(
            extract_features(source_text, suspicious_text, citation_context_text=citation_context_text, use_semantic=use_semantic)
        )
    return feature_rows
