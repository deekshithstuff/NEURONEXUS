from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.plagiarism.classifier import PlagiarismClassifier, evaluate_classifier
from backend.plagiarism.feature_extractor import extract_feature_matrix
from backend.plagiarism.semantic_matcher import DEFAULT_MODEL, semantic_status
from backend.training.prepare_dataset import prepare_dataset


def _tune_threshold(labels: list[int], probabilities: list[float]) -> float:
    from sklearn.metrics import f1_score

    best_threshold = 0.5
    best_f1 = -1.0
    for step in range(5, 96, 5):
        threshold = step / 100
        predictions = [int(score >= threshold) for score in probabilities]
        score = f1_score(labels, predictions, zero_division=0)
        if score > best_f1 or (score == best_f1 and threshold > best_threshold):
            best_f1 = float(score)
            best_threshold = threshold
    return best_threshold


def _classification_metrics(labels: list[int], predictions: list[int]) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score

    tn, fp, fn, tp = (int(value) for value in confusion_matrix(labels, predictions, labels=[0, 1]).ravel())
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
    }


def _baseline_score(features: dict[str, Any]) -> float:
    return max(
        float(features["exact_phrase_match"]),
        float(features["word_overlap"]),
        float(features["char_overlap"]),
        float(features["tfidf_cosine"]),
    )


def _vectorizer_for(train_rows: list[dict[str, Any]]) -> Any:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for TF-IDF and model training; install backend\\requirements.txt."
        ) from exc
    training_corpus = [
        text
        for row in train_rows
        for text in (row["source_text"], row["suspicious_text"])
    ]
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        min_df=1,
        max_features=100_000,
        norm="l2",
    )
    try:
        vectorizer.fit(training_corpus)
    except ValueError as exc:
        raise ValueError(f"Unable to build training TF-IDF vocabulary: {exc}") from exc
    return vectorizer


def train_model(
    dataset_path: str | Path,
    *,
    output_dir: str | Path = "models/plagiarism",
    random_state: int = 42,
    use_semantic: bool = False,
) -> dict[str, Any]:
    splits = prepare_dataset(dataset_path, random_state=random_state)
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    test_rows = splits["test"]
    if not all((train_rows, validation_rows, test_rows)):
        raise ValueError("Training requires non-empty independent train, validation, and test splits.")
    if {row["label"] for row in train_rows} != {0, 1}:
        raise ValueError("Training split must contain both labels 0 and 1.")

    semantic_available = semantic_status()["status"] == "available"
    if use_semantic and not semantic_available:
        raise RuntimeError("Semantic training requested, but sentence-transformers is unavailable.")

    vectorizer = _vectorizer_for(train_rows)
    train_features = extract_feature_matrix(
        train_rows,
        tfidf_vectorizer=vectorizer,
        use_semantic=use_semantic,
    )
    validation_features = extract_feature_matrix(
        validation_rows,
        tfidf_vectorizer=vectorizer,
        use_semantic=use_semantic,
    )
    labels_train = [int(row["label"]) for row in train_rows]
    labels_validation = [int(row["label"]) for row in validation_rows]
    labels_test = [int(row["label"]) for row in test_rows]
    try:
        from sklearn.dummy import DummyClassifier
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for the training baseline; install backend\\requirements.txt."
        ) from exc

    metadata = {
        **splits["metadata"],
        "model": "LogisticRegression",
        "semantic_model": DEFAULT_MODEL if use_semantic else None,
        "tfidf": {
            "analyzer": "word",
            "ngram_range": [1, 2],
            "max_features": 100_000,
            "fit_scope": "train split only",
        },
        "feature_names": list(train_features[0]),
        "random_state": random_state,
        "training_metadata": {
            "python_model": "scikit-learn LogisticRegression",
            "class_weight": "balanced",
            "semantic_feature_enabled": use_semantic,
        },
    }
    model = PlagiarismClassifier(
        random_state=random_state,
        metadata=metadata,
    ).fit(
        train_features,
        labels_train,
        tfidf_vectorizer=vectorizer,
        use_semantic=use_semantic,
    )
    validation_scores = model.predict_positive_scores(validation_features)
    model.threshold = _tune_threshold(labels_validation, validation_scores)

    # The test partition is touched only after fitting and validation threshold tuning.
    started = perf_counter()
    test_metrics = evaluate_classifier(model, test_rows)
    test_runtime_seconds = perf_counter() - started

    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit([[0.0] for _ in train_rows], labels_train)
    dummy_predictions = [int(value) for value in dummy.predict([[0.0] for _ in test_rows])]

    test_features = extract_feature_matrix(
        test_rows,
        tfidf_vectorizer=vectorizer,
        use_semantic=use_semantic,
    )
    validation_baseline_scores = [_baseline_score(row) for row in validation_features]
    lexical_threshold = _tune_threshold(labels_validation, validation_baseline_scores)
    lexical_predictions = [
        int(_baseline_score(features) >= lexical_threshold) for features in test_features
    ]
    metrics = {
        "test": test_metrics,
        "dummy_baseline": _classification_metrics(labels_test, dummy_predictions),
        "exact_lexical_baseline": _classification_metrics(labels_test, lexical_predictions),
        "thresholds": {
            "logistic_regression": model.threshold,
            "exact_lexical_baseline": lexical_threshold,
            "selected_on": "validation split only",
        },
        "test_runtime_seconds": round(test_runtime_seconds, 6),
        "source_retrieval": {
            "status": "not measured",
            "detail": "Pair classification test pairs do not define a complete retrieval candidate corpus.",
        },
    }
    metadata["evaluation"] = metrics
    model.metadata = metadata
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "plagiarism_classifier.joblib"
    model.save(model_path)
    (output / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"model_path": str(model_path), "metadata": metadata}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and independently evaluate the plagiarism classifier.")
    parser.add_argument("dataset", type=str, help="CSV, JSON, or JSONL labeled passage-pair data.")
    parser.add_argument("--output-dir", type=str, default="models/plagiarism")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--semantic", action="store_true", help="Use the optional pretrained semantic embedding feature.")
    args = parser.parse_args()
    result = train_model(
        args.dataset,
        output_dir=args.output_dir,
        random_state=args.seed,
        use_semantic=args.semantic,
    )
    print(json.dumps(result, indent=2))
