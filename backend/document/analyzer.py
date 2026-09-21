from __future__ import annotations

from pathlib import Path

from .parser import DocumentParser


def analyze_document(path: str | Path, document_id: str):
    return DocumentParser().parse(Path(path), document_id)
