from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from backend.plagiarism.preprocessing import ngrams, tokenize

REQUIRED_FIELDS = {
    "source_document_id",
    "suspicious_document_id",
    "source_text",
    "suspicious_text",
    "label",
}
OPTIONAL_GROUP_FIELDS = ("document_group_id", "source_group_id", "derivative_group_id", "group_id")


def _coerce_label(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in {0, 1}:
        return value
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return int(value.strip())
    raise ValueError(f"Labels must be binary integers 0 or 1; received {value!r}.")


def _load_rows(source: Path) -> list[dict[str, Any]]:
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if source.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        with source.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSONL at line {line_number}: {exc}") from exc
        return rows
    if source.suffix.lower() == ".json":
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        raise ValueError("JSON datasets must be a list of pairs or an object with a 'data' list.")
    raise ValueError(f"Unsupported dataset format: {source.suffix}. Use CSV, JSON, or JSONL.")


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Training dataset not found: {source}")
    rows = _load_rows(source)
    validated: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str, str], int] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Dataset row {index} must be an object.")
        missing_fields = REQUIRED_FIELDS - set(row)
        if missing_fields:
            raise ValueError(
                f"Dataset row {index} is missing required fields: {', '.join(sorted(missing_fields))}."
            )
        try:
            label = _coerce_label(row["label"])
        except ValueError as exc:
            raise ValueError(f"Invalid label in dataset row {index}: {exc}") from exc
        source_text = str(row.get("source_text") or "").strip()
        suspicious_text = str(row.get("suspicious_text") or "").strip()
        source_id = str(row.get("source_document_id") or "").strip()
        suspicious_id = str(row.get("suspicious_document_id") or "").strip()
        if not all((source_text, suspicious_text, source_id, suspicious_id)):
            raise ValueError(
                f"Dataset row {index} must have non-empty document IDs and passage texts."
            )
        key = (
            min(source_id, suspicious_id),
            max(source_id, suspicious_id),
            min(_normalized_fingerprint(source_text), _normalized_fingerprint(suspicious_text)),
            max(_normalized_fingerprint(source_text), _normalized_fingerprint(suspicious_text)),
        )
        if key in seen and seen[key] != label:
            raise ValueError(f"Conflicting labels for duplicate source/suspicious pair in dataset row {index}.")
        if key in seen:
            continue
        seen[key] = label
        item: dict[str, Any] = {
            "source_document_id": source_id,
            "suspicious_document_id": suspicious_id,
            "source_text": source_text,
            "suspicious_text": suspicious_text,
            "label": label,
            "source_start": row.get("source_start"),
            "source_end": row.get("source_end"),
            "suspicious_start": row.get("suspicious_start"),
            "suspicious_end": row.get("suspicious_end"),
            "citation_context": row.get("citation_context"),
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        }
        for field in OPTIONAL_GROUP_FIELDS:
            if row.get(field):
                item[field] = str(row[field])
        validated.append(item)
    if not validated:
        raise ValueError(
            f"No usable passage pairs in {source}; required fields are {', '.join(sorted(REQUIRED_FIELDS))}."
        )
    return validated


def _normalized_fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\W+", " ", normalized, flags=re.UNICODE).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _group_ids(rows: list[dict[str, Any]]) -> list[str]:
    parent: dict[str, str] = {}
    text_nodes: dict[str, str] = {}
    text_shingles: dict[str, set[str]] = {}
    text_tokens: dict[str, list[str]] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    def add_text(document_node: str, text: str) -> None:
        fingerprint = _normalized_fingerprint(text)
        text_node = text_nodes.setdefault(fingerprint, f"text:{fingerprint}")
        union(document_node, text_node)
        tokens = tokenize(text)
        if fingerprint not in text_tokens:
            text_tokens[fingerprint] = tokens
            if len(tokens) >= 10:
                text_shingles[fingerprint] = set(ngrams(tokens, 5))

    document_nodes: list[tuple[str, str]] = []
    for row in rows:
        source_id = f"doc:{row['source_document_id']}"
        suspicious_id = f"doc:{row['suspicious_document_id']}"
        union(source_id, suspicious_id)
        document_nodes.append((source_id, suspicious_id))
        for field in OPTIONAL_GROUP_FIELDS:
            group_value = row.get(field)
            if group_value:
                union(source_id, f"group:{field}:{group_value}")
                union(suspicious_id, f"group:{field}:{group_value}")
        add_text(source_id, row["source_text"])
        add_text(suspicious_id, row["suspicious_text"])

    shingle_documents: dict[str, list[str]] = defaultdict(list)
    for fingerprint in sorted(text_shingles):
        candidates: Counter[str] = Counter()
        for shingle in text_shingles[fingerprint]:
            prior_texts = shingle_documents[shingle]
            if len(prior_texts) <= 100:
                candidates.update(prior_texts)
        left_shingles = text_shingles[fingerprint]
        for candidate, shared_shingles in candidates.most_common(500):
            right_shingles = text_shingles[candidate]
            if (
                shared_shingles < 4
                or shared_shingles / min(len(left_shingles), len(right_shingles)) < 0.65
            ):
                continue
            if (
                SequenceMatcher(
                    None,
                    text_tokens[fingerprint],
                    text_tokens[candidate],
                    autojunk=False,
                ).ratio()
                >= 0.85
            ):
                union(text_nodes[fingerprint], text_nodes[candidate])
        for shingle in left_shingles:
            shingle_documents[shingle].append(fingerprint)

    return [find(source_id) for source_id, _ in document_nodes]


def _split_metadata(rows: list[dict[str, Any]], group_ids: list[str]) -> dict[str, Any]:
    return {
        "examples": len(rows),
        "document_groups": len(set(group_ids)),
        "class_distribution": {
            "0": sum(row["label"] == 0 for row in rows),
            "1": sum(row["label"] == 1 for row in rows),
        },
        "source_document_count": len({row["source_document_id"] for row in rows}),
        "suspicious_document_count": len({row["suspicious_document_id"] for row in rows}),
    }


def split_by_document_groups(
    rows: list[dict[str, Any]],
    *,
    random_state: int = 42,
    attempts: int = 2000,
) -> dict[str, list[dict[str, Any]]]:
    if len(rows) < 12 or {int(row["label"]) for row in rows} != {0, 1}:
        raise ValueError(
            "At least 12 valid labeled pairs containing both classes are required. "
            "Provide additional independently sourced and labeled documents."
        )
    groups = _group_ids(rows)
    unique_groups = sorted(set(groups))
    if len(unique_groups) < 6:
        raise ValueError(
            f"Only {len(unique_groups)} independent document groups remain after leakage grouping; "
            "at least 6 are required to create independent train/validation/test splits. "
            "Add labeled examples from more unrelated source and suspicious documents."
        )

    rows_by_group: dict[str, list[dict[str, Any]]] = {}
    for row, group in zip(rows, groups):
        rows_by_group.setdefault(group, []).append(row)
    train_group_count = max(1, round(len(unique_groups) * 0.65))
    validation_group_count = max(1, round(len(unique_groups) * 0.15))
    best: dict[str, list[dict[str, Any]]] | None = None
    best_penalty: float | None = None
    for attempt in range(attempts):
        shuffled_groups = list(unique_groups)
        random.Random(random_state + attempt).shuffle(shuffled_groups)
        train_groups = set(shuffled_groups[:train_group_count])
        validation_groups = set(
            shuffled_groups[train_group_count : train_group_count + validation_group_count]
        )
        test_groups = set(shuffled_groups) - train_groups - validation_groups
        assignments = {
            "train": [row for group in train_groups for row in rows_by_group[group]],
            "validation": [row for group in validation_groups for row in rows_by_group[group]],
            "test": [row for group in test_groups for row in rows_by_group[group]],
        }
        if any({row["label"] for row in split} != {0, 1} for split in assignments.values()):
            continue
        # Favor expected proportions without compromising group separation or class coverage.
        penalty = sum(
            abs(len(assignments[name]) / len(rows) - target)
            for name, target in (("train", 0.65), ("validation", 0.15), ("test", 0.20))
        )
        if best_penalty is None or penalty < best_penalty:
            best = assignments
            best_penalty = penalty
    if best is None:
        raise ValueError(
            "Could not create independent train, validation, and test sets with both labels in every split. "
            "Add more labeled examples from independent document groups and ensure each class is represented."
        )
    return best


def split_by_source_group(
    rows: list[dict[str, Any]],
    *,
    random_state: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    split = split_by_document_groups(rows, random_state=random_state)
    return split["train"], split["validation"], split["test"]


def prepare_dataset(
    path: str | Path,
    *,
    random_state: int = 42,
) -> dict[str, Any]:
    source = Path(path)
    rows = load_dataset(source)
    splits = split_by_document_groups(rows, random_state=random_state)
    group_ids = _group_ids(rows)
    group_lookup = {id(row): group for row, group in zip(rows, group_ids)}
    summaries = {
        name: _split_metadata(split, [group_lookup[id(row)] for row in split])
        for name, split in splits.items()
    }
    return {
        **splits,
        "metadata": {
            "dataset_version": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_file": source.name,
            "random_state": random_state,
            "total_examples": len(rows),
            "splits": summaries,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate and split labeled passage-pair data.")
    parser.add_argument("dataset", type=str, help="Dataset path (CSV, JSON, or JSONL).")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    dataset = prepare_dataset(args.dataset, random_state=args.seed)
    print(json.dumps(dataset["metadata"], indent=2))
