from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "source_document_id",
    "suspicious_document_id",
    "source_text",
    "suspicious_text",
    "label",
}


def _coerce_label(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return 1 if int(value) > 0 else 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "suspicious", "copy", "plagiarized"}:
            return 1
        if lowered in {"0", "false", "no", "clean", "non-match", "original"}:
            return 0
    raise ValueError(f"Unsupported label value: {value!r}")


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    elif source.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                rows.append(json.loads(raw))
    elif source.suffix.lower() == ".json":
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        rows = payload if isinstance(payload, list) else payload.get("data", [])
    else:
        raise ValueError(f"Unsupported dataset format for {source}")

    validated: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            continue
        label = _coerce_label(row.get("label"))
        source_text = str(row.get("source_text") or "")
        suspicious_text = str(row.get("suspicious_text") or "")
        if not source_text.strip() or not suspicious_text.strip():
            continue
        key = (
            str(row.get("source_document_id") or ""),
            str(row.get("suspicious_document_id") or ""),
            source_text.strip()[:200],
            suspicious_text.strip()[:200],
        )
        if key in seen:
            continue
        seen.add(key)
        cleaned = {
            "source_document_id": str(row.get("source_document_id") or "unknown-source"),
            "suspicious_document_id": str(row.get("suspicious_document_id") or "unknown-target"),
            "source_text": source_text,
            "suspicious_text": suspicious_text,
            "label": label,
            "source_start": row.get("source_start"),
            "source_end": row.get("source_end"),
            "suspicious_start": row.get("suspicious_start"),
            "suspicious_end": row.get("suspicious_end"),
            "citation_context": row.get("citation_context"),
            "metadata": row.get("metadata", {}),
        }
        validated.append(cleaned)
    return validated


def split_by_source_group(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row["source_document_id"]
        groups.setdefault(key, []).append(row)

    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for _, group_rows in groups.items():
        group_rows = list(group_rows)
        if not group_rows:
            continue
        if len(group_rows) <= 2:
            train.extend(group_rows)
            continue
        pivot = max(1, len(group_rows) // 3)
        train.extend(group_rows[:-pivot])
        validation.extend(group_rows[-pivot:-max(1, pivot // 2) or None])
        test.extend(group_rows[-max(1, pivot // 2) :])
    return train, validation, test


def prepare_dataset(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    rows = load_dataset(path)
    train, validation, test = split_by_source_group(rows)
    return {"train": train, "validation": validation, "test": test}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare a plagiarism training dataset.")
    parser.add_argument("dataset", type=str, help="Path to CSV, JSON, or JSONL dataset.")
    args = parser.parse_args()
    dataset = prepare_dataset(args.dataset)
    print(json.dumps({"train": len(dataset["train"]), "validation": len(dataset["validation"]), "test": len(dataset["test"])}, indent=2))
