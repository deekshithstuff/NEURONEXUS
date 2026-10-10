"""Loading of the clearly identified comparison corpus.

The checker only ever reports matches against sources it can identify by name.
By default that is the bundled synthetic corpus shipped with PaperPilot. An
operator may point ``PAPERPILOT_PLAGIARISM_CORPUS_DIR`` at a directory of their
own licensed texts; every file in that directory becomes an identifiable source.
No user manuscript is ever added to the corpus, so matches never leak content
between accounts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BUNDLED_CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "sources.json"


def load_corpus(extra_dir: str | None = None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    sources.extend(_load_bundled())
    directory = extra_dir if extra_dir is not None else os.getenv("PAPERPILOT_PLAGIARISM_CORPUS_DIR")
    sources.extend(_load_directory(directory))
    return _deduplicate(sources)


def _load_bundled() -> list[dict[str, Any]]:
    if not BUNDLED_CORPUS_PATH.exists():
        return []
    try:
        payload = json.loads(BUNDLED_CORPUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [_normalize_source(entry) for entry in payload.get("sources", []) if entry.get("text")]


def _load_directory(directory: str | None) -> list[dict[str, Any]]:
    if not directory:
        return []
    path = Path(directory)
    if not path.is_dir():
        return []
    sources: list[dict[str, Any]] = []
    for entry in sorted(path.iterdir()):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix not in {".txt", ".md", ".json"}:
            continue
        try:
            if suffix == ".json":
                sources.extend(_load_json_source(entry))
            else:
                text = entry.read_text(encoding="utf-8", errors="ignore")
                sources.append(_normalize_source({
                    "id": f"file-{entry.stem}",
                    "title": entry.stem.replace("_", " ").replace("-", " ").title(),
                    "source_type": "custom_corpus_file",
                    "url": None,
                    "text": text,
                }))
        except OSError:
            continue
    return sources


def _load_json_source(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict) and isinstance(payload.get("sources"), list):
        return [_normalize_source(entry) for entry in payload["sources"] if entry.get("text")]
    if isinstance(payload, list):
        return [_normalize_source(entry) for entry in payload if entry.get("text")]
    return []


def _normalize_source(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or "source"),
        "title": str(entry.get("title") or entry.get("id") or "Untitled source"),
        "authors": list(entry.get("authors") or []),
        "year": entry.get("year"),
        "url": entry.get("url"),
        "source_type": str(entry.get("source_type") or "corpus"),
        "text": str(entry.get("text") or ""),
    }


def _deduplicate(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for source in sources:
        if source["id"] in seen or not source["text"].strip():
            continue
        seen.add(source["id"])
        unique.append(source)
    return unique


def corpus_info(sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = sources if sources is not None else load_corpus()
    custom_dir = os.getenv("PAPERPILOT_PLAGIARISM_CORPUS_DIR")
    demo_count = sum(source.get("source_type") == "bundled_synthetic" for source in sources)
    custom_count = len(sources) - demo_count
    return {
        "name": "Identified PaperPilot comparison corpus",
        "source_count": len(sources),
        "synthetic_demo_source_count": demo_count,
        "custom_source_count": custom_count,
        "custom_corpus_dir_configured": bool(custom_dir),
        "description": (
            "The checker compares only with identified bundled synthetic demonstration texts and "
            "operator-provided local sources. It does not search all published research or the internet. "
            "Manuscripts are never added to the corpus or shared between accounts."
        ),
    }
