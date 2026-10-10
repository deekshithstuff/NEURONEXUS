from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.plagiarism.classifier import PlagiarismClassifier, evaluate_classifier as evaluate_model
from backend.plagiarism.feature_extractor import extract_features
from backend.training.prepare_dataset import prepare_dataset


def evaluate_model_artifact(dataset_path: str | Path, model_path: str | Path) -> dict[str, object]:
    prepared = prepare_dataset(dataset_path)
    rows = prepared["test"] or prepared["validation"] or prepared["train"]
    classifier = PlagiarismClassifier.load(model_path)
    metrics = evaluate_model(classifier, rows)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a trained plagiarism classifier.")
    parser.add_argument("dataset", type=str, help="Dataset path (CSV, JSON, or JSONL).")
    parser.add_argument("model", type=str, help="Path to the saved classifier artifact.")
    args = parser.parse_args()
    print(json.dumps(evaluate_model_artifact(args.dataset, args.model), indent=2))
