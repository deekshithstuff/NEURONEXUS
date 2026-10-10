from __future__ import annotations

import math
import pickle
from pathlib import Path
from typing import Any

from .feature_extractor import FEATURE_NAMES, extract_feature_matrix

ARTIFACT_VERSION = 1


class PlagiarismClassifier:
    """Supervised logistic-regression passage-pair model."""

    def __init__(
        self,
        *,
        threshold: float = 0.5,
        random_state: int = 42,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.threshold = threshold
        self.random_state = random_state
        self.metadata = metadata or {}
        self.feature_names = list(FEATURE_NAMES)
        self.model: Any = None
        self.tfidf_vectorizer: Any = None
        self.use_semantic = False

    def fit(
        self,
        X: list[dict[str, Any]],
        y: list[int],
        *,
        tfidf_vectorizer: Any,
        use_semantic: bool = False,
    ) -> "PlagiarismClassifier":
        if len(X) != len(y) or not X:
            raise ValueError("Training features and labels must have the same non-zero length.")
        if set(y) != {0, 1}:
            raise ValueError("Supervised training requires examples from both binary classes 0 and 1.")
        if tfidf_vectorizer is None or not hasattr(tfidf_vectorizer, "vocabulary_"):
            raise ValueError("Training requires a fitted TF-IDF vectorizer.")
        if use_semantic and not self.metadata.get("semantic_model"):
            raise ValueError(
                "Semantic training requires the embedding model identity in classifier metadata."
            )
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:
            raise RuntimeError(
                "scikit-learn is required for supervised training; install backend\\requirements.txt."
            ) from exc
        self.tfidf_vectorizer = tfidf_vectorizer
        self.use_semantic = use_semantic
        matrix = self._matrix(X)
        self.model = LogisticRegression(
            random_state=self.random_state,
            max_iter=1000,
            class_weight="balanced",
            solver="liblinear",
        )
        self.model.fit(matrix, y)
        return self

    def _matrix(self, X: list[dict[str, Any]]) -> list[list[float]]:
        for index, row in enumerate(X):
            missing = set(self.feature_names) - set(row)
            if missing:
                raise ValueError(
                    f"Feature row {index} is missing model features: {', '.join(sorted(missing))}"
                )
        return [[float(row[name]) for name in self.feature_names] for row in X]

    def predict_proba(self, X: list[dict[str, Any]]) -> list[list[float]]:
        if self.model is None:
            raise ValueError("Classifier artifact has no fitted logistic-regression model.")
        return self.model.predict_proba(self._matrix(X)).tolist()

    def predict(self, X: list[dict[str, Any]]) -> list[int]:
        return [int(probabilities[1] >= self.threshold) for probabilities in self.predict_proba(X)]

    def predict_positive_scores(self, X: list[dict[str, Any]]) -> list[float]:
        return [float(probabilities[1]) for probabilities in self.predict_proba(X)]

    def save(self, path: str | Path) -> str:
        if self.model is None:
            raise ValueError("Cannot save an untrained classifier.")
        if self.tfidf_vectorizer is None:
            raise ValueError("Cannot save a classifier without its fitted TF-IDF vectorizer.")
        try:
            import joblib
        except ImportError as exc:
            raise RuntimeError(
                "joblib is required to save the classifier; install backend\\requirements.txt."
            ) from exc
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "artifact_version": ARTIFACT_VERSION,
                "classifier": self.model,
                "tfidf_vectorizer": self.tfidf_vectorizer,
                "feature_names": self.feature_names,
                "threshold": self.threshold,
                "random_state": self.random_state,
                "use_semantic": self.use_semantic,
                "metadata": self.metadata,
            },
            target,
        )
        return str(target)

    @classmethod
    def load(cls, path: str | Path) -> "PlagiarismClassifier":
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Trained plagiarism classifier not found: {target}")
        try:
            import joblib
        except ImportError as exc:
            raise RuntimeError(
                "joblib is required to load the classifier; install backend\\requirements.txt."
            ) from exc
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:
            raise RuntimeError(
                "scikit-learn is required to load the trained classifier; install backend\\requirements.txt."
            ) from exc
        try:
            payload = joblib.load(target)
        except (OSError, EOFError, pickle.UnpicklingError, ImportError, AttributeError, ValueError, TypeError) as exc:
            raise ValueError(f"Could not deserialize classifier artifact {target}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Classifier artifact must contain a metadata dictionary: {target}")
        required_fields = {
            "artifact_version",
            "classifier",
            "tfidf_vectorizer",
            "feature_names",
            "threshold",
            "random_state",
            "use_semantic",
            "metadata",
        }
        missing_fields = required_fields - set(payload)
        if missing_fields:
            raise ValueError(
                f"Classifier artifact is missing fields: {', '.join(sorted(missing_fields))}."
            )
        if payload.get("artifact_version") != ARTIFACT_VERSION:
            raise ValueError(f"Unsupported classifier artifact version in {target}.")
        model = payload.get("classifier")
        vectorizer = payload.get("tfidf_vectorizer")
        if not isinstance(model, LogisticRegression) or not hasattr(vectorizer, "vocabulary_"):
            raise ValueError(f"Invalid or incomplete trained classifier artifact: {target}")
        try:
            threshold = float(payload["threshold"])
            random_state = int(payload["random_state"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Classifier artifact has invalid threshold or random state: {target}") from exc
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Classifier artifact threshold must be between 0 and 1: {target}")
        if not isinstance(payload["use_semantic"], bool):
            raise ValueError(f"Classifier artifact semantic setting is invalid: {target}")
        if not isinstance(payload["metadata"], dict):
            raise ValueError(f"Classifier artifact metadata must be a dictionary: {target}")
        artifact = cls(
            threshold=threshold,
            random_state=random_state,
            metadata=dict(payload.get("metadata") or {}),
        )
        artifact.model = model
        artifact.tfidf_vectorizer = vectorizer
        feature_names = payload.get("feature_names")
        if not isinstance(feature_names, list) or not all(
            isinstance(name, str) for name in feature_names
        ):
            raise ValueError("The artifact has invalid feature names.")
        artifact.feature_names = feature_names
        artifact.use_semantic = bool(payload.get("use_semantic", False))
        if artifact.feature_names != list(FEATURE_NAMES):
            raise ValueError("The artifact feature schema does not match the current inference schema.")
        if getattr(model, "n_features_in_", None) != len(FEATURE_NAMES):
            raise ValueError("The classifier artifact model width does not match its feature schema.")
        if list(getattr(model, "classes_", [])) != [0, 1]:
            raise ValueError("The classifier artifact does not contain both binary label classes.")
        if artifact.use_semantic and not artifact.metadata.get("semantic_model"):
            raise ValueError("The semantic classifier artifact does not identify its embedding model.")
        return artifact


def train_classifier(
    training_pairs: list[dict[str, Any]],
    *,
    tfidf_vectorizer: Any,
    threshold: float = 0.5,
    random_state: int = 42,
    use_semantic: bool = False,
    metadata: dict[str, Any] | None = None,
) -> PlagiarismClassifier:
    classifier_metadata = dict(metadata or {})
    if use_semantic and not classifier_metadata.get("semantic_model"):
        from .semantic_matcher import DEFAULT_MODEL

        classifier_metadata["semantic_model"] = DEFAULT_MODEL
    features = extract_feature_matrix(
        training_pairs,
        tfidf_vectorizer=tfidf_vectorizer,
        use_semantic=use_semantic,
        semantic_model=classifier_metadata.get("semantic_model"),
    )
    labels = [int(pair["label"]) for pair in training_pairs]
    return PlagiarismClassifier(
        threshold=threshold,
        random_state=random_state,
        metadata=classifier_metadata,
    ).fit(
        features,
        labels,
        tfidf_vectorizer=tfidf_vectorizer,
        use_semantic=use_semantic,
    )


def evaluate_classifier(
    classifier: PlagiarismClassifier,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot evaluate on an empty independent test set.")
    try:
        from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required to evaluate the classifier; install backend\\requirements.txt."
        ) from exc
    features = extract_feature_matrix(
        rows,
        tfidf_vectorizer=classifier.tfidf_vectorizer,
        use_semantic=classifier.use_semantic,
        semantic_model=classifier.metadata.get("semantic_model"),
    )
    labels = [int(row["label"]) for row in rows]
    predictions = classifier.predict(features)
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "predictions": predictions,
        "labels": labels,
    }


def feature_matrix(
    rows: list[dict[str, Any]],
    *,
    tfidf_vectorizer: Any,
    use_semantic: bool = False,
) -> list[dict[str, float | int]]:
    return extract_feature_matrix(
        rows,
        tfidf_vectorizer=tfidf_vectorizer,
        use_semantic=use_semantic,
    )
