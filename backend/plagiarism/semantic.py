"""Optional Sentence Transformers semantic matching engine.

Semantic matching is opt-in and best-effort. When ``sentence-transformers`` is
not installed it reports an explicit unavailable status instead of guessing, so
results never imply a comparison that did not happen. Semantic similarities are
labelled ``semantic_related`` and are excluded from plagiarism counts because
topical similarity alone is not evidence of plagiarism.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.82
MAX_MANUSCRIPT_PASSAGES = 400
MAX_CORPUS_SENTENCES = 4000

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


def _get_model(model_name: str):
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


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
            "detail": "Semantic matching found no additional comparisons to run.",
        }
    try:
        import numpy as np

        model = _get_model(DEFAULT_MODEL)
        manuscript_embeddings = model.encode(
            [passage["text"] for passage in candidates],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        corpus_embeddings = model.encode(
            [sentence["text"] for sentence in corpus_candidates],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        similarities = manuscript_embeddings @ corpus_embeddings.T
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        return [], {
            "engine": "semantic",
            "status": "failed",
            "detail": f"Semantic model could not be loaded or run: {exc}",
        }

    matches: list[dict[str, Any]] = []
    for row, passage in enumerate(candidates):
        best_index = int(np.argmax(similarities[row]))
        best_score = float(similarities[row][best_index])
        if best_score < SIMILARITY_THRESHOLD:
            continue
        corpus_sentence = corpus_candidates[best_index]
        source = corpus_sentence["source"]
        classification = _semantic_classification(passage)
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
                "method": "semantic",
                "similarity": round(best_score, 4),
                "coverage": None,
                "matched_words": 0,
                "attributed": bool(passage["attributed"]),
                "quoted": bool(passage["quoted"]),
                "classification": classification,
                "matched_text": corpus_sentence["text"],
                "note": (
                    "Semantic similarity indicates topical or paraphrased similarity with an identified source; "
                    "it is not evidence of plagiarism on its own."
                ),
            }
        )
    return matches, {
        "engine": "semantic",
        "status": "completed",
        "detail": f"Compared {len(candidates)} passages against {len(corpus_candidates)} corpus sentences.",
    }


def _semantic_classification(passage: dict[str, Any]) -> str:
    if passage["quoted"] and passage["attributed"]:
        return "attributed_quotation"
    if passage["quoted"]:
        return "quotation"
    if passage["attributed"]:
        return "cited_match"
    return "semantic_related"
