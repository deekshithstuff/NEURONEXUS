from __future__ import annotations

from typing import Any

from .citation_context import has_citation_context
from .exact_matcher import ExactMatcher
from .lexical_matcher import TfidfSimilarityIndex, lexical_similarity_features
from .preprocessing import tokenize
from .semantic_matcher import semantic_similarity, semantic_status

FEATURE_NAMES = (
    "exact_phrase_match",
    "word_overlap",
    "char_overlap",
    "tfidf_cosine",
    "semantic_cosine",
    "distinctive_phrase_ratio",
    "passage_length_ratio",
    "citation_context_indicator",
)


class FeatureExtractor:
    def __init__(
        self,
        *,
        tfidf_vectorizer: Any | TfidfSimilarityIndex | None = None,
        use_semantic: bool = False,
        semantic_model: str | None = None,
    ) -> None:
        self.tfidf_vectorizer = tfidf_vectorizer
        self.use_semantic = use_semantic
        self.semantic_model = semantic_model
        self.exact_matcher = ExactMatcher(min_tokens=3, threshold=0.6)

    def extract(
        self,
        source_text: str,
        suspicious_text: str,
        *,
        citation_context_text: str | None = None,
        citation_present: bool | None = None,
    ) -> dict[str, float | int]:
        lexical = lexical_similarity_features(
            source_text,
            suspicious_text,
            tfidf_vectorizer=self.tfidf_vectorizer,
        )
        exact_phrase_match = float(bool(self.exact_matcher.match(source_text, suspicious_text)))
        semantic_score = 0.0
        if self.use_semantic:
            status = semantic_status()
            if status["status"] != "available":
                raise RuntimeError(
                    f"Semantic feature is unavailable: {status.get('detail', 'embedding model unavailable')}"
                )
            semantic_result = semantic_similarity(
                source_text,
                suspicious_text,
                model_name=self.semantic_model,
            )
            if semantic_result is None:
                raise RuntimeError("Semantic feature computation returned no embedding score.")
            semantic_score = semantic_result
        source_tokens = tokenize(source_text)
        suspicious_tokens = tokenize(suspicious_text)
        passage_length_ratio = (
            min(len(source_tokens), len(suspicious_tokens))
            / max(len(source_tokens), len(suspicious_tokens))
            if source_tokens and suspicious_tokens
            else 0.0
        )
        return {
            "exact_phrase_match": exact_phrase_match,
            "word_overlap": float(lexical["word_overlap"]),
            "char_overlap": float(lexical["char_overlap"]),
            "tfidf_cosine": float(lexical["tfidf_cosine"]),
            "semantic_cosine": float(semantic_score),
            "distinctive_phrase_ratio": float(lexical["distinctive_phrase_ratio"]),
            "passage_length_ratio": float(passage_length_ratio),
            "citation_context_indicator": int(
                citation_present
                if citation_present is not None
                else has_citation_context(citation_context_text or "")
            ),
        }


def extract_features(
    source_text: str,
    suspicious_text: str,
    *,
    citation_context_text: str | None = None,
    citation_present: bool | None = None,
    tfidf_vectorizer: Any | TfidfSimilarityIndex | None = None,
    use_semantic: bool = False,
    semantic_model: str | None = None,
) -> dict[str, float | int]:
    return FeatureExtractor(
        tfidf_vectorizer=tfidf_vectorizer,
        use_semantic=use_semantic,
        semantic_model=semantic_model,
    ).extract(
        source_text,
        suspicious_text,
        citation_context_text=citation_context_text,
        citation_present=citation_present,
    )


def extract_feature_matrix(
    rows: list[dict[str, Any]],
    *,
    tfidf_vectorizer: Any | TfidfSimilarityIndex | None = None,
    use_semantic: bool = False,
    semantic_model: str | None = None,
) -> list[dict[str, float | int]]:
    extractor = FeatureExtractor(
        tfidf_vectorizer=tfidf_vectorizer,
        use_semantic=use_semantic,
        semantic_model=semantic_model,
    )
    return [
        extractor.extract(
            str(row.get("source_text") or ""),
            str(row.get("suspicious_text") or ""),
            citation_context_text=row.get("citation_context"),
            citation_present=row.get("citation_present"),
        )
        for row in rows
    ]
