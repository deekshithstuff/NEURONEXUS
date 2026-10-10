"""Plagiarism scan orchestration and persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.database import connection, fetch_all, fetch_one
from backend.journal.rules import get_journal_rules

from . import external
from .corpus import corpus_info, load_corpus
from .engine import _candidate_indices, build_report, extract_manuscript_passages, index_corpus, match_passages
from .engine import analyze as analyze_internal
from .external import ExternalScanError
from .inference import classifier_status, score_retrieved_pairs
from .semantic import semantic_matches, semantic_status

ALLOWED_ENGINES = {"lexical", "semantic"}
ALLOWED_PROVIDERS = {"internal", "external"}

SCAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS plagiarism_scans (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'internal',
    engines_json TEXT,
    consent_external INTEGER NOT NULL DEFAULT 0,
    report_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
"""


class ScanError(ValueError):
    """Raised for invalid or unauthorized plagiarism scan requests."""


def ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(SCAN_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan_config() -> dict[str, Any]:
    semantic = semantic_status()
    return {
        "corpus": corpus_info(),
        "semantic": semantic,
        "classifier": classifier_status(),
        "external": external.external_status(),
        "engines": [
            {"id": "lexical", "label": "Exact and near-exact matching", "available": True},
            {
                "id": "semantic",
                "label": "Semantic similarity (Sentence Transformers)",
                "available": semantic["status"] == "available",
            },
        ],
        "default_engines": ["lexical"],
        "disclaimer": (
            "Similarity is not a verdict. The checker reports overlap with identified sources only and "
            "does not prove plagiarism by itself."
        ),
    }


def start_scan(
    document_id: str,
    user: dict[str, str],
    *,
    provider: str = "internal",
    engines: list[str] | None = None,
    consent_external: bool = False,
) -> dict[str, Any]:
    ensure_schema()
    provider = (provider or "internal").strip().lower()
    engines = [engine.strip().lower() for engine in (engines or ["lexical"]) if engine.strip()]
    if provider not in ALLOWED_PROVIDERS:
        raise ScanError(f"Unsupported provider '{provider}'. Choose internal or external.")
    if not engines:
        engines = ["lexical"]
    invalid = sorted(set(engines) - ALLOWED_ENGINES)
    if invalid:
        raise ScanError(f"Unsupported engine(s): {', '.join(invalid)}.")
    if not fetch_one(
        "SELECT 1 FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user["id"]),
    ):
        raise ScanError("Document not found.")
    document = fetch_one(
        "SELECT analysis_json FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user["id"]),
    )
    if not document or not document["analysis_json"]:
        raise ScanError("Analyze the manuscript before running a similarity scan.")

    if provider == "external":
        status = external.external_status()
        if not status["configured"]:
            raise ScanError("No external plagiarism provider is configured.")
        if not consent_external:
            raise ScanError("Explicit consent is required before sending the manuscript to an external provider.")

    scan_id = f"PLG-{uuid.uuid4().hex[:10].upper()}"
    timestamp = _now()
    with connection() as conn:
        conn.execute(
            "INSERT INTO plagiarism_scans "
            "(id, document_id, user_id, status, provider, engines_json, consent_external, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                document_id,
                user["id"],
                "queued",
                provider,
                json.dumps(engines),
                1 if consent_external else 0,
                timestamp,
                timestamp,
            ),
        )
    return {"scan_id": scan_id, "document_id": document_id, "status": "queued", "provider": provider, "engines": engines}


def run_scan(scan_id: str) -> None:
    ensure_schema()
    row = fetch_one("SELECT * FROM plagiarism_scans WHERE id = ?", (scan_id,))
    if row is None:
        return
    _update(scan_id, status="running")
    try:
        document = fetch_one("SELECT * FROM documents WHERE id = ?", (row["document_id"],))
        if document is None or not document["analysis_json"]:
            raise ScanError("The document is no longer available for scanning.")
        analysis = json.loads(document["analysis_json"])
        engines = json.loads(row["engines_json"] or "[]")
        provider = row["provider"] or "internal"
        citation_style = _citation_style(document["selected_journal_id"])
        sources = load_corpus()
        if provider == "external":
            report = _run_external_scan(analysis, engines, citation_style, sources)
        else:
            report = analyze_internal(analysis, sources, engines, citation_style)
        report["scan_id"] = scan_id
        _update(scan_id, status="completed", report=report)
    except (ScanError, ExternalScanError, ValueError) as exc:
        _update(scan_id, status="failed", error=str(exc) or "The similarity scan failed.")
    except Exception as exc:  # pragma: no cover - defensive
        _update(scan_id, status="failed", error=f"The similarity scan failed: {exc}")


def _run_external_scan(
    analysis: dict[str, Any],
    engines: list[str],
    citation_style: str | None,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    text = "\n\n".join(analysis.get("paragraphs") or [])
    passages, excluded = extract_manuscript_passages(analysis)
    total_words = sum(len(passage["tokens"]) for passage in passages)
    corpus_sentences, inverted = index_corpus(sources)
    matches = match_passages(passages, corpus_sentences, inverted)
    candidate_indices = [_candidate_indices(passage["tokens"], inverted) for passage in passages]
    classifier_results, classifier_engine_status = score_retrieved_pairs(
        passages,
        corpus_sentences,
        candidate_indices,
    )
    engine_status: list[dict[str, Any]] = [
        {
            "engine": "lexical",
            "status": "completed" if sources else "unavailable",
            "detail": (
                "Local exact and near-exact matching against the identified corpus."
                if sources
                else "No local comparison sources were loaded; no local source search was performed."
            ),
        }
    ]
    engine_status.append(classifier_engine_status)
    if "semantic" in engines:
        semantic, status = semantic_matches(passages, matches, corpus_sentences)
        matches.extend(semantic)
        engine_status.append(status)
    external_result = external.fetch_external_report(text, title=analysis.get("title"))
    matches.extend(external_result["matches"])
    engine_status.append(
        {
            "engine": external_result["provider"],
            "status": "completed",
            "detail": f"External provider returned {len(external_result['matches'])} match(es).",
        }
    )
    report = build_report(
        document_id=analysis.get("document_id") or "",
        provider=external_result["provider"],
        matches=matches,
        total_words=total_words,
        excluded=excluded,
        engine_status=engine_status,
        sources=sources,
        citation_style=citation_style,
        analysis=analysis,
        classifier_results=classifier_results,
        classifier_status=classifier_engine_status,
    )
    report["external_summary"] = external_result.get("external_summary", {})
    return report


def _citation_style(journal_id: str | None) -> str | None:
    try:
        return get_journal_rules(journal_id or "nature").get("citation_style")
    except ValueError:
        return None


def get_scan(scan_id: str, user: dict[str, str]) -> dict[str, Any]:
    ensure_schema()
    row = fetch_one(
        "SELECT * FROM plagiarism_scans WHERE id = ? AND user_id = ?",
        (scan_id, user["id"]),
    )
    if row is None:
        raise ScanError("Scan not found.")
    return _serialize(row)


def list_scans(document_id: str, user: dict[str, str]) -> dict[str, Any]:
    ensure_schema()
    if not fetch_one(
        "SELECT 1 FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user["id"]),
    ):
        raise ScanError("Document not found.")
    rows = fetch_all(
        "SELECT id, status, provider, engines_json, error, created_at, updated_at "
        "FROM plagiarism_scans WHERE document_id = ? AND user_id = ? ORDER BY created_at DESC, id",
        (document_id, user["id"]),
    )
    return {"document_id": document_id, "scans": [_serialize(row, include_report=False) for row in rows]}


def download_report(scan_id: str, user: dict[str, str]) -> tuple[str, str]:
    scan = get_scan(scan_id, user)
    if scan["status"] != "completed" or not scan["report"]:
        raise ScanError("The similarity report is not ready yet.")
    filename = f"paperpilot-plagiarism-{scan_id}.json"
    return filename, json.dumps(scan["report"], indent=2)


def _update(scan_id: str, *, status: str, report: dict | None = None, error: str | None = None) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE plagiarism_scans SET status = ?, report_json = COALESCE(?, report_json), "
            "error = ?, updated_at = ? WHERE id = ?",
            (status, json.dumps(report) if report is not None else None, error, _now(), scan_id),
        )


def _serialize(row, *, include_report: bool = True) -> dict[str, Any]:
    payload = {
        "scan_id": row["id"],
        "document_id": row["document_id"] if "document_id" in row.keys() else None,
        "status": row["status"],
        "provider": row["provider"],
        "engines": json.loads(row["engines_json"] or "[]"),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_report:
        payload["report"] = json.loads(row["report_json"]) if row["report_json"] else None
    return payload
