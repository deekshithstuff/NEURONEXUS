from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.plagiarism.classifier import PlagiarismClassifier, evaluate_classifier
from backend.plagiarism.feature_extractor import extract_feature_matrix
from backend.plagiarism.preprocessing import tokenize
from backend.training.prepare_dataset import prepare_dataset
from backend.training.train_classifier import _baseline_score, _classification_metrics, _tune_threshold


def _evaluate_source_retrieval(test_rows: list[dict[str, Any]], limit: int = 5) -> dict[str, Any]:
    source_docs: dict[str, str] = {}
    for row in test_rows:
        source_docs.setdefault(row["source_document_id"], row["source_text"])
    positive_rows = [row for row in test_rows if row["label"] == 1]
    if not positive_rows or len(source_docs) < 2:
        return {
            "status": "not measurable",
            "detail": "Need positive test pairs and multiple source documents for retrieval evaluation.",
        }

    hits_at_one = 0
    hits_at_k = 0
    for row in positive_rows:
        target_tokens = set(tokenize(row["suspicious_text"]))
        ranked = sorted(
            source_docs.items(),
            key=lambda item: (
                -len(target_tokens & set(tokenize(item[1]))) / max(len(target_tokens | set(tokenize(item[1]))), 1),
                item[0],
            ),
        )
        ranked_ids = [doc_id for doc_id, _ in ranked]
        hits_at_one += int(ranked_ids[0] == row["source_document_id"])
        hits_at_k += int(row["source_document_id"] in ranked_ids[:limit])
    count = len(positive_rows)
    return {
        "status": "measured on test split source texts",
        "positive_pairs": count,
        "source_document_count": len(source_docs),
        "recall_at_1": hits_at_one / count,
        f"recall_at_{limit}": hits_at_k / count,
        "scope": "Dataset-internal retrieval only; not retrieval from the internet or all publications.",
    }


def evaluate_model_artifact(
    dataset_path: str | Path,
    model_path: str | Path,
    *,
    random_state: int = 42,
) -> dict[str, Any]:
    try:
        from sklearn.dummy import DummyClassifier
        from sklearn.metrics import precision_recall_curve
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for evaluation; install backend\\requirements.txt."
        ) from exc
    prepared = prepare_dataset(dataset_path, random_state=random_state)
    rows = prepared["test"]
    if not rows:
        raise ValueError("Independent test split is empty; refusing to evaluate on training or validation data.")
    classifier = PlagiarismClassifier.load(model_path)
    if (
        classifier.metadata.get("dataset_version") != prepared["metadata"]["dataset_version"]
        or classifier.random_state != random_state
    ):
        raise ValueError(
            "The provided model was trained against a different dataset version or split seed; "
            "evaluate with the original dataset and --seed."
        )

    started = perf_counter()
    classifier_metrics = evaluate_classifier(classifier, rows)
    runtime = perf_counter() - started
    features = extract_feature_matrix(
        rows,
        tfidf_vectorizer=classifier.tfidf_vectorizer,
        use_semantic=classifier.use_semantic,
    )
    labels = [int(row["label"]) for row in rows]

    training_rows = prepared["train"]
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit([[0.0] for _ in training_rows], [int(row["label"]) for row in training_rows])
    dummy_predictions = [int(value) for value in dummy.predict([[0.0] for _ in rows])]

    validation_rows = prepared["validation"]
    validation_features = extract_feature_matrix(
        validation_rows,
        tfidf_vectorizer=classifier.tfidf_vectorizer,
        use_semantic=classifier.use_semantic,
    )
    validation_labels = [int(row["label"]) for row in validation_rows]
    lexical_threshold = _tune_threshold(
        validation_labels,
        [_baseline_score(feature) for feature in validation_features],
    )
    lexical_predictions = [
        int(_baseline_score(feature) >= lexical_threshold) for feature in features
    ]

    scores = classifier.predict_positive_scores(features)
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    threshold_curve = [
        {
            "threshold": float(threshold),
            "precision": float(precision[index + 1]),
            "recall": float(recall[index + 1]),
        }
        for index, threshold in enumerate(thresholds)
    ]
    return {
        "dataset_version": prepared["metadata"]["dataset_version"],
        "test_split": prepared["metadata"]["splits"]["test"],
        "model": _classification_metrics(labels, classifier_metrics["predictions"]),
        "dummy_baseline": _classification_metrics(labels, dummy_predictions),
        "exact_lexical_baseline": _classification_metrics(labels, lexical_predictions),
        "lexical_threshold_selected_on_validation": lexical_threshold,
        "precision_recall_thresholds": threshold_curve,
        "positive_score_calibration": {
            "brier_score": sum((score - label) ** 2 for score, label in zip(scores, labels)) / len(labels),
            "is_calibrated": False,
            "note": "Brier score is reported as a diagnostic; no probability calibration was fitted.",
        },
        "test_runtime_seconds": round(runtime, 6),
        "source_retrieval": _evaluate_source_retrieval(rows),
        "predictions": classifier_metrics["predictions"],
        "labels": labels,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a saved classifier on its independent test split.")
    parser.add_argument("dataset", type=str, help="Dataset path (CSV, JSON, or JSONL).")
    parser.add_argument("model", type=str, help="Path to the saved classifier artifact.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(evaluate_model_artifact(args.dataset, args.model, random_state=args.seed), indent=2))
