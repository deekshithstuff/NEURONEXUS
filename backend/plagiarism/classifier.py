from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from .feature_extractor import extract_features

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    joblib = None

try:
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
except Exception:  # pragma: no cover - optional dependency
    DummyClassifier = None  # type: ignore[assignment]
    LogisticRegression = None  # type: ignore[assignment]


class RuleBasedClassifier:
    def __init__(self, *, threshold: float = 0.55):
        self.threshold = threshold
        self.feature_names: list[str] = [
            "exact_phrase_match",
            "word_overlap",
            "char_overlap",
            "tfidf_cosine",
            "semantic_cosine",
            "distinctive_phrase_ratio",
            "passage_length_ratio",
            "citation_context_indicator",
        ]

    def fit(self, X: list[dict[str, Any]], y: list[int]) -> "RuleBasedClassifier":
        self._train_count = len(X)
        return self

    def predict(self, X: list[dict[str, Any]]) -> list[int]:
        return [int(self._score(row) >= self.threshold) for row in X]

    def predict_proba(self, X: list[dict[str, Any]]) -> list[list[float]]:
        probabilities: list[list[float]] = []
        for row in X:
            score = self._score(row)
            prob_1 = min(1.0, max(0.0, score))
            probabilities.append([1.0 - prob_1, prob_1])
        return probabilities

    def _score(self, row: dict[str, Any]) -> float:
        score = 0.0
        score += float(row.get("exact_phrase_match", 0.0)) * 0.45
        score += float(row.get("word_overlap", 0.0)) * 0.15
        score += float(row.get("char_overlap", 0.0)) * 0.10
        score += float(row.get("tfidf_cosine", 0.0)) * 0.20
        score += float(row.get("semantic_cosine", 0.0)) * 0.10
        if float(row.get("citation_context_indicator", 0)):
            score *= 0.8
        return min(1.0, score)

    def score(self, X: list[dict[str, Any]], y: list[int]) -> float:
        predictions = self.predict(X)
        matches = sum(int(pred == actual) for pred, actual in zip(predictions, y))
        return matches / max(len(y), 1)


class PlagiarismClassifier:
    """Classifier wrapper that uses sklearn when available and falls back to a rule-based scorer."""

    def __init__(self, *, threshold: float = 0.55, random_state: int = 42):
        self.threshold = threshold
        self.random_state = random_state
        self.model: Any = None
        self.feature_names: list[str] = [
            "exact_phrase_match",
            "word_overlap",
            "char_overlap",
            "tfidf_cosine",
            "semantic_cosine",
            "distinctive_phrase_ratio",
            "passage_length_ratio",
            "citation_context_indicator",
        ]
        self._backend = "rule-based"

    def fit(self, X: list[dict[str, Any]], y: list[int]) -> "PlagiarismClassifier":
        if LogisticRegression is not None:
            self.model = LogisticRegression(random_state=self.random_state, max_iter=500)
            matrix = [[float(row.get(name, 0.0)) for name in self.feature_names] for row in X]
            self.model.fit(matrix, y)
            self._backend = "logistic-regression"
            return self

        self.model = RuleBasedClassifier(threshold=self.threshold)
        self.model.fit(X, y)
        self._backend = "rule-based"
        return self

    def predict(self, X: list[dict[str, Any]]) -> list[int]:
        if self.model is None:
            raise ValueError("The classifier has not been fitted yet.")
        if self._backend == "logistic-regression":
            matrix = [[float(row.get(name, 0.0)) for name in self.feature_names] for row in X]
            return [int(value) for value in self.model.predict(matrix)]
        return self.model.predict(X)

    def predict_proba(self, X: list[dict[str, Any]]) -> list[list[float]]:
        if self.model is None:
            raise ValueError("The classifier has not been fitted yet.")
        if self._backend == "logistic-regression":
            matrix = [[float(row.get(name, 0.0)) for name in self.feature_names] for row in X]
            return self.model.predict_proba(matrix).tolist()
        return self.model.predict_proba(X)

    def score(self, X: list[dict[str, Any]], y: list[int]) -> float:
        if self.model is None:
            raise ValueError("The classifier has not been fitted yet.")
        predictions = self.predict(X)
        matches = sum(int(pred == actual) for pred, actual in zip(predictions, y))
        return matches / max(len(y), 1)

    def save(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "feature_names": self.feature_names,
            "backend": self._backend,
            "threshold": self.threshold,
            "random_state": self.random_state,
        }
        if joblib is not None:
            joblib.dump(payload, target)
        else:
            with target.open("wb") as handle:
                pickle.dump(payload, handle)
        return str(target)

    @classmethod
    def load(cls, path: str | Path) -> "PlagiarismClassifier":
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Classifier artifact not found: {target}")
        if joblib is not None:
            payload = joblib.load(target)
        else:
            with target.open("rb") as handle:
                payload = pickle.load(handle)
        artifact = cls(threshold=float(payload.get("threshold", 0.55)), random_state=int(payload.get("random_state", 42)))
        artifact.model = payload["model"]
        artifact.feature_names = payload.get("feature_names", artifact.feature_names)
        artifact._backend = payload.get("backend", artifact._backend)
        return artifact


def train_classifier(training_pairs: list[dict[str, Any]], *, threshold: float = 0.55, random_state: int = 42) -> PlagiarismClassifier:
    classifier = PlagiarismClassifier(threshold=threshold, random_state=random_state)
    features = []
    labels = []
    for pair in training_pairs:
        row = pair.get("features")
        if row is None:
            row = extract_features(pair["source_text"], pair["suspicious_text"], citation_context_text=pair.get("citation_context"))
        features.append(row)
        labels.append(int(pair.get("label", 0)))
    classifier.fit(features, labels)
    return classifier


def evaluate_classifier(classifier: PlagiarismClassifier, rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = [row.get("features") or extract_features(row["source_text"], row["suspicious_text"], citation_context_text=row.get("citation_context")) for row in rows]
    labels = [int(row.get("label", 0)) for row in rows]
    predictions = classifier.predict(features)
    accuracy = sum(int(pred == label) for pred, label in zip(predictions, labels)) / max(len(labels), 1)
    return {"accuracy": round(accuracy, 4), "predictions": predictions, "labels": labels}


def feature_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row.get("features") or extract_features(row["source_text"], row["suspicious_text"], citation_context_text=row.get("citation_context")) for row in rows]
