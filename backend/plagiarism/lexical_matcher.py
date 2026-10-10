from __future__ import annotations

from collections import Counter
import math
from typing import Any

from .preprocessing import ngrams, normalize_text, tokenize

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity
except ImportError:  # pragma: no cover - dependency installation error is surfaced on use
    TfidfVectorizer = None  # type: ignore[assignment,misc]
    sklearn_cosine_similarity = None  # type: ignore[assignment]


def word_ngrams(text: str, n: int = 2) -> list[str]:
    return ngrams(tokenize(text), n)


def char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = normalize_text(text)
    if len(cleaned) < n:
        return []
    return [cleaned[index : index + n] for index in range(len(cleaned) - n + 1)]


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def cosine_similarity(vec_a: Counter[str] | dict[str, float], vec_b: Counter[str] | dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    left = Counter(vec_a)
    right = Counter(vec_b)
    numerator = sum(left[key] * right.get(key, 0) for key in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


class TfidfSimilarityIndex:
    """TF-IDF model fitted once on a defined corpus and reused for every query."""

    def __init__(
        self,
        *,
        ngram_range: tuple[int, int] = (1, 2),
        analyzer: str = "word",
        min_df: int | float = 1,
        max_features: int | None = 100_000,
    ) -> None:
        if TfidfVectorizer is None:
            raise RuntimeError("scikit-learn is required for TF-IDF similarity.")
        self.vectorizer = TfidfVectorizer(
            ngram_range=ngram_range,
            analyzer=analyzer,
            min_df=min_df,
            max_features=max_features,
            lowercase=True,
            strip_accents="unicode",
            norm="l2",
            dtype=float,
        )
        self._fitted = False
        self.corpus_size = 0

    def fit(self, corpus: list[str]) -> "TfidfSimilarityIndex":
        documents = [normalize_text(text) for text in corpus if normalize_text(text)]
        if not documents:
            raise ValueError("Cannot fit TF-IDF on an empty corpus.")
        self.vectorizer.fit(documents)
        self._fitted = True
        self.corpus_size = len(documents)
        return self

    def similarity(self, left: str, right: str) -> float:
        if not self._fitted:
            raise RuntimeError("TF-IDF index must be fitted before computing similarity.")
        if not left.strip() or not right.strip():
            return 0.0
        vectors = self.vectorizer.transform([normalize_text(left), normalize_text(right)])
        return float(sklearn_cosine_similarity(vectors[0], vectors[1])[0, 0])

    def transform(self, texts: list[str]) -> Any:
        if not self._fitted:
            raise RuntimeError("TF-IDF index must be fitted before transforming text.")
        return self.vectorizer.transform([normalize_text(text) for text in texts])

    @classmethod
    def from_vectorizer(cls, vectorizer: Any) -> "TfidfSimilarityIndex":
        instance = cls(
            ngram_range=vectorizer.ngram_range,
            analyzer=vectorizer.analyzer,
            min_df=vectorizer.min_df,
            max_features=vectorizer.max_features,
        )
        instance.vectorizer = vectorizer
        instance._fitted = True
        return instance


def tfidf_cosine_similarity(
    source_text: str,
    suspicious_text: str,
    *,
    vectorizer: Any | TfidfSimilarityIndex | None = None,
    ngram_range: tuple[int, int] = (1, 2),
) -> float:
    """Compare using a fitted corpus vectorizer; never fit an inference-time pair."""
    if vectorizer is None:
        return 0.0
    if isinstance(vectorizer, TfidfSimilarityIndex):
        return round(vectorizer.similarity(source_text, suspicious_text), 4)
    if not hasattr(vectorizer, "vocabulary_"):
        raise RuntimeError("The supplied TF-IDF vectorizer has not been fitted.")
    if not source_text.strip() or not suspicious_text.strip():
        return 0.0
    try:
        pair_vectors = vectorizer.transform([normalize_text(source_text), normalize_text(suspicious_text)])
        return round(float(sklearn_cosine_similarity(pair_vectors[0], pair_vectors[1])[0, 0]), 4)
    except ValueError:
        # An empty vocabulary in a legitimate fitted corpus contains no usable
        # evidence; unlike pairwise fitting, this does not change the model.
        return 0.0


def lexical_similarity_features(
    source_text: str,
    suspicious_text: str,
    *,
    tfidf_vectorizer: Any | TfidfSimilarityIndex | None = None,
    word_ngram_range: tuple[int, int] = (1, 2),
    char_ngram_range: tuple[int, int] = (3, 5),
) -> dict[str, float]:
    source_word_grams = {
        gram
        for n in range(word_ngram_range[0], word_ngram_range[1] + 1)
        for gram in word_ngrams(source_text, n)
    }
    suspicious_word_grams = {
        gram
        for n in range(word_ngram_range[0], word_ngram_range[1] + 1)
        for gram in word_ngrams(suspicious_text, n)
    }
    source_chars = {
        gram
        for n in range(char_ngram_range[0], char_ngram_range[1] + 1)
        for gram in char_ngrams(source_text, n)
    }
    suspicious_chars = {
        gram
        for n in range(char_ngram_range[0], char_ngram_range[1] + 1)
        for gram in char_ngrams(suspicious_text, n)
    }
    word_overlap = jaccard_similarity(source_word_grams, suspicious_word_grams)
    char_overlap = jaccard_similarity(source_chars, suspicious_chars)
    tfidf_score = tfidf_cosine_similarity(source_text, suspicious_text, vectorizer=tfidf_vectorizer)
    source_tokens = set(tokenize(source_text))
    suspicious_tokens = set(tokenize(suspicious_text))
    distinctive_phrase_ratio = (
        len(source_tokens ^ suspicious_tokens) / max(len(source_tokens | suspicious_tokens), 1)
    )
    return {
        "word_overlap": round(word_overlap, 4),
        "char_overlap": round(char_overlap, 4),
        "tfidf_cosine": round(tfidf_score, 4),
        "distinctive_phrase_ratio": round(distinctive_phrase_ratio, 4),
    }


def compare_lexical_similarity(
    source_text: str,
    suspicious_text: str,
    *,
    tfidf_vectorizer: Any | TfidfSimilarityIndex | None = None,
) -> dict[str, float]:
    return lexical_similarity_features(
        source_text,
        suspicious_text,
        tfidf_vectorizer=tfidf_vectorizer,
    )
