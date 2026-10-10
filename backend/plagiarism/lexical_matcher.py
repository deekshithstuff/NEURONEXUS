from __future__ import annotations

from collections import Counter
import math

from .preprocessing import ngrams, normalize_text, tokenize


def word_ngrams(text: str, n: int = 2) -> list[str]:
    tokens = tokenize(text)
    return ngrams(tokens, n)


def char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = normalize_text(text)
    if len(cleaned) < n:
        return []
    return [cleaned[index : index + n] for index in range(len(cleaned) - n + 1)]


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


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


def tfidf_cosine_similarity(source_text: str, suspicious_text: str, *, ngram_range: tuple[int, int] = (1, 2)) -> float:
    def vectorize(text: str) -> Counter[str]:
        counter: Counter[str] = Counter()
        for n in range(ngram_range[0], ngram_range[1] + 1):
            for gram in word_ngrams(text, n):
                counter[gram] += 1
        return counter

    left = vectorize(source_text)
    right = vectorize(suspicious_text)
    if not left and not right:
        return 0.0
    score = cosine_similarity(left, right)
    return round(score, 4)


def lexical_similarity_features(source_text: str, suspicious_text: str) -> dict[str, float]:
    source_tokens = set(tokenize(source_text))
    suspicious_tokens = set(tokenize(suspicious_text))
    word_overlap = jaccard_similarity(source_tokens, suspicious_tokens)
    char_overlap = jaccard_similarity(set(char_ngrams(source_text, 3)), set(char_ngrams(suspicious_text, 3)))
    tfidf_score = tfidf_cosine_similarity(source_text, suspicious_text)
    source_unique = source_tokens - suspicious_tokens
    suspicious_unique = suspicious_tokens - source_tokens
    distinctive_phrase_ratio = (len(source_unique) + len(suspicious_unique)) / max(len(source_tokens | suspicious_tokens), 1)
    return {
        "word_overlap": round(word_overlap, 4),
        "char_overlap": round(char_overlap, 4),
        "tfidf_cosine": round(tfidf_score, 4),
        "distinctive_phrase_ratio": round(distinctive_phrase_ratio, 4),
    }


def compare_lexical_similarity(source_text: str, suspicious_text: str) -> dict[str, float]:
    return lexical_similarity_features(source_text, suspicious_text)
