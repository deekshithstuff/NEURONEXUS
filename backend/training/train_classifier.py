from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.plagiarism.classifier import PlagiarismClassifier, feature_matrix
from backend.plagiarism.feature_extractor import extract_features
from backend.training.prepare_dataset import prepare_dataset


def train_model(dataset_path: str | Path, *, output_dir: str | Path = "models/plagiarism") -> dict[str, object]:
    splits = prepare_dataset(dataset_path)
    train_rows = splits["train"]
    if not train_rows:
        raise ValueError("Training dataset is empty after validation and deduplication.")

    features = []
    labels = []
    for row in train_rows:
        feature_row = row.get("features") or extract_features(row["source_text"], row["suspicious_text"], citation_context_text=row.get("citation_context"))
        features.append(feature_row)
        labels.append(int(row["label"]))

    classifier = PlagiarismClassifier(threshold=0.55)
    classifier.fit(features, labels)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    model_path = target / "plagiarism_classifier.joblib"
    classifier.save(model_path)
    metadata = {
        "feature_names": classifier.feature_names,
        "num_training_rows": len(train_rows),
        "backend": classifier._backend,
        "random_state": classifier.random_state,
    }
    (target / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"model_path": str(model_path), "metadata": metadata}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a plagiarism classifier.")
    parser.add_argument("dataset", type=str, help="Dataset path (CSV, JSON, or JSONL).")
    parser.add_argument("--output-dir", type=str, default="models/plagiarism", help="Output directory for the model artifact.")
    args = parser.parse_args()
    result = train_model(args.dataset, output_dir=args.output_dir)
    print(json.dumps(result, indent=2))
