from __future__ import annotations

import hashlib
import math
import os
from typing import Any

DEFAULT_MODEL = os.getenv("PAPERPILOT_EMBEDDING_MODEL") or os.getenv("PAPERPILOT_PLAGIARISM_MODEL") or os.getenv("PAPERPILOT_PLAGIARISM_EMBEDDING_MODEL") or "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.82

_MODEL_CACHE: dict[str, Any] = {}


def semantic_status() -> dict[str, Any]:
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return {
            "engine": "semantic",
            "status": "unavailable",
            "detail": "sentence-transformers is not installed; semantic matching is skipped.",
        }
    return {
        "engine": "semantic",
        "status": "available",
        "detail": "Sentence Transformers semantic matching is available.",
    }


def _hash_vector(text: str, dim: int = 64) -> list[float]:
    vector = [0.0] * dim
    normalized = text.lower().strip()
    if not normalized:
        return vector
    for word in normalized.split():
        digest = hashlib.md5(word.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _encode_with_model(texts: list[str], model_name: str) -> list[list[float]]:
    if model_name in _MODEL_CACHE:
        model = _MODEL_CACHE[model_name]
    else:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
    embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return embeddings.tolist()


def encode_texts(texts: list[str], *, model_name: str | None = None) -> list[list[float]]:
    model_name = model_name or DEFAULT_MODEL
    if not texts:
        return []
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return [_hash_vector(text) for text in texts]
    try:
        return _encode_with_model(texts, model_name)
    except Exception:
        return [_hash_vector(text) for text in texts]


def semantic_similarity(source_text: str, suspicious_text: str, *, model_name: str | None = None) -> float:
    if not source_text or not suspicious_text:
        return 0.0
    vectors = encode_texts([source_text, suspicious_text], model_name=model_name)
    if len(vectors) < 2:
        return 0.0
    return round(_cosine_similarity(vectors[0], vectors[1]), 4)


def semantic_matches(source_texts: list[str], suspicious_texts: list[str], *, model_name: str | None = None) -> list[float]:
    vectors = encode_texts(source_texts + suspicious_texts, model_name=model_name)
    if len(vectors) < 2:
        return [0.0] * max(len(source_texts), len(suspicious_texts))
    return [
        round(_cosine_similarity(vectors[index], vectors[index + len(source_texts)]), 4)
        for index in range(len(source_texts))
        if index + len(source_texts) < len(vectors)
    ]
