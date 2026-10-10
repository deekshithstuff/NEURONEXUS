from __future__ import annotations

from typing import Any


def score_similarity(features: dict[str, Any]) -> float:
    score = 0.0
    score += float(features.get("exact_phrase_match", 0.0)) * 0.30
    score += float(features.get("word_overlap", 0.0)) * 0.20
    score += float(features.get("char_overlap", 0.0)) * 0.10
    score += float(features.get("tfidf_cosine", 0.0)) * 0.25
    score += float(features.get("semantic_cosine", 0.0)) * 0.10
    score += float(features.get("distinctive_phrase_ratio", 0.0)) * 0.05
    return round(min(1.0, max(0.0, score)), 4)


def classify_similarity(features: dict[str, Any], *, threshold: float = 0.55) -> str:
    if score_similarity(features) >= threshold:
        return "suspicious"
    return "clean"


def aggregate_scores(rows: list[dict[str, Any]]) -> list[float]:
    return [score_similarity(row) for row in rows]
