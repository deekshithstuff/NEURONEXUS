"""Pretrained semantic similarity, deliberately separate from plagiarism verdicts."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from .preprocessing import normalize_text, split_passages

DEFAULT_MODEL = (
    os.getenv("PAPERPILOT_EMBEDDING_MODEL")
    or os.getenv("PAPERPILOT_PLAGIARISM_MODEL")
    or "sentence-transformers/all-MiniLM-L6-v2"
)
SIMILARITY_THRESHOLD = 0.82
MAX_MANUSCRIPT_PASSAGES = 400
MAX_CORPUS_SENTENCES = 4000

_MODEL_CACHE: dict[str, Any] = {}
_SOURCE_EMBEDDING_CACHE: dict[tuple[str, str], Any] = {}


def semantic_status() -> dict[str, Any]:
    try:
        import sentence_transformers  # noqa: F401
    except Exception as exc:
        return {
            "engine": "semantic",
            "status": "unavailable",
            "model": DEFAULT_MODEL,
            "detail": f"sentence-transformers is unavailable ({exc}); semantic similarity was not computed.",
        }
    return {
        "engine": "semantic",
        "status": "available",
        "model": DEFAULT_MODEL,
        "detail": "Pretrained general-purpose sentence embeddings are available; they are not plagiarism-trained.",
    }


def _get_model(model_name: str) -> Any:
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def encode_texts(texts: list[str], *, model_name: str | None = None) -> Any:
    if not texts:
        return []
    model_name = model_name or DEFAULT_MODEL
    if semantic_status()["status"] != "available":
        raise RuntimeError("Semantic embeddings are unavailable because sentence-transformers is not installed.")
    model = _get_model(model_name)
    normalized = [normalize_text(text) for text in texts]
    chunk_groups = [split_passages(text, max_chars=1500, overlap=150) or [text] for text in normalized]
    flattened = [chunk for group in chunk_groups for chunk in group]
    chunk_embeddings = model.encode(
        flattened,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    import numpy as np

    aggregated = []
    offset = 0
    for group in chunk_groups:
        group_vectors = chunk_embeddings[offset : offset + len(group)]
        offset += len(group)
        mean = group_vectors.mean(axis=0)
        norm = np.linalg.norm(mean)
        aggregated.append(mean / norm if norm else mean)
    return np.asarray(aggregated)


def semantic_similarity(source_text: str, suspicious_text: str, *, model_name: str | None = None) -> float | None:
    if not source_text.strip() or not suspicious_text.strip():
        return 0.0
    if semantic_status()["status"] != "available":
        return None
    vectors = encode_texts([source_text, suspicious_text], model_name=model_name)
    return float(vectors[0] @ vectors[1])


def _source_embeddings(corpus_sentences: list[dict[str, Any]], model_name: str) -> Any:
    digest = hashlib.sha256(
        "\0".join(
            f"{item['source']['id']}\0{item['text']}" for item in corpus_sentences
        ).encode("utf-8")
    ).hexdigest()
    key = (model_name, digest)
    if key not in _SOURCE_EMBEDDING_CACHE:
        _SOURCE_EMBEDDING_CACHE[key] = encode_texts(
            [item["text"] for item in corpus_sentences],
            model_name=model_name,
        )
    return _SOURCE_EMBEDDING_CACHE[key]


def semantic_matches(
    passages: list[dict[str, Any]],
    existing_matches: list[dict[str, Any]],
    corpus_sentences: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = semantic_status()
    if status["status"] != "available":
        return [], status

    already_matched = {
        (match["location"]["paragraph_index"], match["location"]["sentence_index"])
        for match in existing_matches
    }
    candidates = [
        passage
        for passage in passages
        if len(passage["tokens"]) >= 6
        and (passage["paragraph_index"], passage["sentence_index"]) not in already_matched
    ][:MAX_MANUSCRIPT_PASSAGES]
    corpus_candidates = corpus_sentences[:MAX_CORPUS_SENTENCES]
    if not candidates or not corpus_candidates:
        return [], {
            "engine": "semantic",
            "status": "completed",
            "model": DEFAULT_MODEL,
            "detail": "There were no eligible passage comparisons.",
        }

    try:
        import numpy as np

        manuscript_embeddings = encode_texts([passage["text"] for passage in candidates])
        corpus_embeddings = _source_embeddings(corpus_candidates, DEFAULT_MODEL)
        similarities = manuscript_embeddings @ corpus_embeddings.T
    except Exception as exc:
        return [], {
            "engine": "semantic",
            "status": "failed",
            "model": DEFAULT_MODEL,
            "detail": f"Semantic model could not be loaded or run: {exc}",
        }

    matches: list[dict[str, Any]] = []
    for row, passage in enumerate(candidates):
        best_index = int(np.argmax(similarities[row]))
        best_score = float(similarities[row, best_index])
        if best_score < SIMILARITY_THRESHOLD:
            continue
        corpus_sentence = corpus_candidates[best_index]
        source = corpus_sentence["source"]
        matches.append(
            {
                "passage": passage["text"],
                "location": {
                    "paragraph_index": passage["paragraph_index"],
                    "paragraph_number": passage["paragraph_number"],
                    "sentence_index": passage["sentence_index"],
                    "section_heading": passage["section_heading"],
                    "section_type": passage["section_type"],
                    "char_start": passage["char_start"],
                    "char_end": passage["char_end"],
                },
                "source": {
                    "id": source["id"],
                    "title": source["title"],
                    "url": source["url"],
                    "source_type": source["source_type"],
                    "authors": source["authors"],
                    "year": source["year"],
                },
                "source_location": {
                    "char_start": corpus_sentence["char_start"],
                    "char_end": corpus_sentence["char_end"],
                },
                "method": "semantic",
                "similarity": round(best_score, 4),
                "coverage": None,
                "matched_words": 0,
                "attributed": bool(passage["attributed"]),
                "quoted": bool(passage["quoted"]),
                "classification": "semantic_related",
                "matched_text": corpus_sentence["text"],
                "note": (
                    "General-purpose semantic similarity indicates related meaning, not textual overlap "
                    "or plagiarism. Verify the identified source manually."
                ),
            }
        )
    return matches, {
        "engine": "semantic",
        "status": "completed",
        "model": DEFAULT_MODEL,
        "detail": f"Compared {len(candidates)} passages against {len(corpus_candidates)} corpus passages.",
    }
