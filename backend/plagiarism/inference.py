"""Cached model loading and inference for retrieved, identified source pairs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .classifier import PlagiarismClassifier
from .feature_extractor import extract_feature_matrix
from .semantic_matcher import semantic_status

DEFAULT_ARTIFACT = (
    Path(__file__).resolve().parents[2] / "models" / "plagiarism" / "plagiarism_classifier.joblib"
)

_CACHED_CLASSIFIER: PlagiarismClassifier | None = None
_CACHED_KEY: tuple[str, int] | None = None


def artifact_path() -> Path:
    configured = os.getenv("PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_ARTIFACT


def load_classifier() -> PlagiarismClassifier:
    global _CACHED_CLASSIFIER, _CACHED_KEY
    path = artifact_path()
    if not path.is_file():
        raise FileNotFoundError(f"Trained plagiarism classifier is not available: {path}")
    key = (str(path.resolve()), path.stat().st_mtime_ns)
    if _CACHED_CLASSIFIER is None or _CACHED_KEY != key:
        _CACHED_CLASSIFIER = PlagiarismClassifier.load(path)
        _CACHED_KEY = key
    return _CACHED_CLASSIFIER


def classifier_status() -> dict[str, Any]:
    path = artifact_path()
    if not path.is_file():
        return {
            "status": "unavailable",
            "detail": "No trained classifier artifact is installed; supervised scoring is not used.",
        }
    try:
        model = load_classifier()
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return {"status": "failed", "detail": f"Classifier artifact could not be loaded: {exc}"}
    if model.use_semantic:
        status = semantic_status()
        if status["status"] != "available":
            return {
                "status": "unavailable",
                "detail": (
                    "The trained classifier requires its semantic embedding feature, but that "
                    f"feature is unavailable: {status.get('detail', 'embedding model unavailable')}"
                ),
                "dataset_version": model.metadata.get("dataset_version"),
            }
    return {
        "status": "available",
        "detail": "Trained logistic-regression model loaded.",
        "dataset_version": model.metadata.get("dataset_version"),
        "feature_names": model.feature_names,
    }


def score_retrieved_pairs(
    passages: list[dict[str, Any]],
    corpus_sentences: list[dict[str, Any]],
    candidate_indices: list[list[int]],
    *,
    limit_per_passage: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_pairs: list[tuple[int, int]] = []
    for passage_index, indices in enumerate(candidate_indices):
        candidate_pairs.extend((passage_index, source_index) for source_index in indices[:limit_per_passage])

    try:
        classifier = load_classifier()
    except FileNotFoundError as exc:
        return [], {
            "engine": "classifier",
            "status": "unavailable",
            "detail": str(exc),
            "candidate_pair_count": len(candidate_pairs),
        }
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return [], {
            "engine": "classifier",
            "status": "failed",
            "detail": str(exc),
            "candidate_pair_count": len(candidate_pairs),
        }

    if not candidate_pairs:
        return [], {
            "engine": "classifier",
            "status": "completed",
            "detail": "The trained model was loaded, but retrieval returned no candidate source pairs.",
            "candidate_pair_count": 0,
        }

    feature_rows = [
        {
            "source_text": corpus_sentences[source_index]["text"],
            "suspicious_text": passages[passage_index]["text"],
            "citation_context": passages[passage_index]["text"]
            if passages[passage_index].get("attributed")
            else "",
            "citation_present": bool(passages[passage_index].get("attributed")),
        }
        for passage_index, source_index in candidate_pairs
    ]
    try:
        features = extract_feature_matrix(
            feature_rows,
            tfidf_vectorizer=classifier.tfidf_vectorizer,
            use_semantic=classifier.use_semantic,
            semantic_model=classifier.metadata.get("semantic_model"),
        )
        probabilities = classifier.predict_positive_scores(features)
        predictions = classifier.predict(features)
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return [], {
            "engine": "classifier",
            "status": "failed",
            "detail": f"Classifier inference could not be completed: {exc}",
            "candidate_pair_count": len(candidate_pairs),
        }
    results = []
    for (passage_index, source_index), feature, probability, prediction in zip(
        candidate_pairs, features, probabilities, predictions
    ):
        passage = passages[passage_index]
        source_record = corpus_sentences[source_index]
        source = source_record["source"]
        results.append(
            {
                "passage_location": {
                    "paragraph_number": passage["paragraph_number"],
                    "sentence_index": passage["sentence_index"],
                    "char_start": passage["char_start"],
                    "char_end": passage["char_end"],
                },
                "source": {
                    "id": source["id"],
                    "title": source["title"],
                    "url": source.get("url"),
                    "source_type": source["source_type"],
                },
                "source_passage": source_record["text"],
                "source_location": {
                    "char_start": source_record.get("char_start"),
                    "char_end": source_record.get("char_end"),
                },
                "suspicious_passage": passage["text"],
                "predicted_label": int(prediction),
                "positive_score": round(float(probability), 4),
                "threshold": classifier.threshold,
                "features": feature,
            }
        )
    results.sort(key=lambda item: (-item["positive_score"], item["source"]["id"]))
    return results, {
        "engine": "classifier",
        "status": "completed",
        "detail": "Supervised predictions are shown only for source passages returned by lexical retrieval.",
        "candidate_pair_count": len(results),
        "model": "LogisticRegression",
        "dataset_version": classifier.metadata.get("dataset_version"),
        "confidence_calibrated": False,
    }
