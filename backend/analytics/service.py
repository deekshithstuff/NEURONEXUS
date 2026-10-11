"""Analytics aggregation for the submission dashboard.

Every indicator is derived from persisted results for the requested document
(and optional version). Values are labeled with their method, inputs, and
interpretation. No indicator is invented: when evidence is missing the indicator
is reported as unavailable.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend import ai_service
from backend.compliance.engine import build_compliance_report
from backend.database import connection, fetch_all, fetch_one
from backend.improvement import service as improvement_service
from backend.journal.rules import get_journal_rules
from backend.security import get_accessible_document


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_id() -> str:
    return f"snap_{uuid.uuid4().hex[:16]}"


def _analysis_result(document_id: str, module: str) -> dict | None:
    row = fetch_one(
        "SELECT payload_json FROM analysis_results WHERE document_id = ? AND module = ?",
        (document_id, module),
    )
    if row is None or not row["payload_json"]:
        return None
    try:
        return json.loads(row["payload_json"])
    except (ValueError, TypeError):
        return None


def _latest_scan(document_id: str, user_id: str) -> dict | None:
    from backend.plagiarism.service import ensure_schema

    ensure_schema()
    row = fetch_one(
        "SELECT id, status, provider, report_json, error, created_at FROM plagiarism_scans "
        "WHERE document_id = ? AND user_id = ? AND status = 'completed' "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (document_id, user_id),
    )
    if row is None or not row["report_json"]:
        return None
    try:
        report = json.loads(row["report_json"])
    except (ValueError, TypeError):
        report = {}
    return {
        "scan_id": row["id"],
        "provider": row["provider"],
        "created_at": row["created_at"],
        "report": report,
    }


def _record_snapshot(document_id: str, version_id: str | None, payload: dict) -> str:
    snapshot_id = _snapshot_id()
    with connection() as conn:
        conn.execute(
            "INSERT INTO analysis_snapshots (id, document_id, version_id, module, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot_id, document_id, version_id, "analytics", json.dumps(payload), _now()),
        )
    return snapshot_id


def _version_history(document_id: str, limit: int = 10) -> list[dict]:
    rows = fetch_all(
        "SELECT id, version_number, label, change_summary, created_at FROM manuscript_versions "
        "WHERE document_id = ? ORDER BY version_number DESC LIMIT ?",
        (document_id, limit),
    )
    return [
        {
            "version_id": row["id"],
            "version_number": row["version_number"],
            "label": row["label"],
            "change_summary": row["change_summary"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _version_analysis(document_id: str, version_id: str | None) -> dict | None:
    if not version_id:
        return None
    row = fetch_one(
        "SELECT analysis_json, version_number, label FROM manuscript_versions WHERE id = ? AND document_id = ?",
        (version_id, document_id),
    )
    if row is None or not row["analysis_json"]:
        return None
    try:
        return {
            "analysis": json.loads(row["analysis_json"]),
            "version_number": row["version_number"],
            "label": row["label"],
        }
    except (ValueError, TypeError):
        return None


def build_dashboard(
    document_id: str,
    user: dict,
    *,
    journal_id: str | None = None,
    version_id: str | None = None,
) -> dict[str, Any]:
    document, role = get_accessible_document(document_id, user, capability="read")
    if not document["analysis_json"]:
        raise ValueError("Analyze the manuscript before opening the analytics dashboard.")

    journal_key = (journal_id or document["selected_journal_id"] or "nature").lower()
    journal = get_journal_rules(journal_key)

    version_source = _version_analysis(document_id, version_id)
    if version_id and version_source is None:
        raise ValueError("The requested version could not be found for this document.")
    analysis = version_source["analysis"] if version_source else json.loads(document["analysis_json"])
    analysis = {**analysis, "document_id": document_id}

    source_format = (analysis.get("metadata") or {}).get("source_format")
    page_count = (analysis.get("metadata") or {}).get("page_count")

    compliance = build_compliance_report(
        analysis,
        journal,
        article_type=document["article_type"] if "article_type" in document.keys() else None,
        source_format=source_format,
        page_count=page_count,
    )
    completeness = ai_service.analyze_completeness(document_id, analysis, journal_key)

    readiness = _analysis_result(document_id, "readiness_report")
    if readiness is None:
        readiness = ai_service.generate_readiness_report(document_id, analysis, None, journal_key)

    improvement = _analysis_result(document_id, "improvement")
    if improvement is None:
        improvement = improvement_service.assess_manuscript(document_id, analysis, journal_key)

    scan = _latest_scan(document_id, user["id"])
    versions = _version_history(document_id)

    current_version = fetch_one(
        "SELECT current_version_id FROM documents WHERE id = ?",
        (document_id,),
    )

    indicators = [
        _readiness_indicator(readiness),
        _compliance_indicator(compliance),
        _completeness_indicator(completeness),
        _similarity_indicator(scan),
        _improvement_indicator(improvement),
    ]

    result = {
        "document_id": document_id,
        "journal_id": journal.get("journal_id"),
        "journal_name": journal.get("journal_name"),
        "version_id": version_id,
        "version_label": version_source.get("label") if version_source else None,
        "version_number": version_source.get("version_number") if version_source else None,
        "access_role": role,
        "indicators": indicators,
        "prioritized_actions": _prioritized_actions(compliance, improvement, readiness),
        "versions": versions,
        "current_version_id": current_version["current_version_id"] if current_version else None,
        "generated_at": _now(),
        "evidence_scope": (
            "All values are computed from this manuscript's parsed content and the latest "
            "persisted analysis results. Items without evidence are marked unavailable."
        ),
        "disclaimer": (
            "These indicators are decision support only. They do not guarantee acceptance, "
            "do not detect plagiarism, and do not verify scientific validity."
        ),
    }
    result["snapshot_id"] = _record_snapshot(document_id, version_id, result)
    return result


def _indicator(
    *,
    key: str,
    label: str,
    available: bool,
    value: Any = None,
    unit: str | None = None,
    method: str = "",
    inputs: str = "",
    interpretation: str = "",
    evidence_type: str = "computed",
    source: str = "",
    details: dict | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "available": available,
        "value": value if available else None,
        "unit": unit,
        "method": method,
        "inputs": inputs,
        "interpretation": interpretation,
        "evidence_type": evidence_type,
        "source": source,
        "details": details or {},
        "assessed_at": _now(),
    }


def _readiness_indicator(readiness: dict) -> dict:
    score = readiness.get("overall_readiness")
    if score is None:
        score = readiness.get("readiness_score", readiness.get("score"))
    return _indicator(
        key="submission_readiness",
        label="Submission readiness",
        available=score is not None,
        value=score,
        unit="score (0-100)",
        method="Deterministic rubric over detected sections, citations, and completeness.",
        inputs="Parsed manuscript + selected journal profile.",
        interpretation="Higher is more complete relative to the configured profile; it is not a journal decision.",
        evidence_type="computed",
        source="readiness_report",
        details={
            "status": readiness.get("status") or readiness.get("readiness_level"),
            "recommendations": readiness.get("recommendations")
            or readiness.get("priority_actions")
            or [],
            "dimension_scores": readiness.get("scores") or readiness.get("dimensions") or {},
            "score_method": readiness.get("score_method"),
        },
    )


def _compliance_indicator(compliance: dict) -> dict:
    return _indicator(
        key="compliance",
        label="Profile compliance",
        available=True,
        value=compliance.get("compliance_score"),
        unit="score (0-100)",
        method="Rule-based checks against the selected journal profile.",
        inputs="Parsed manuscript + journal rules.",
        interpretation="Reflects structural/formatting rules; manual-review rules are excluded from the automated score.",
        evidence_type="computed",
        source=compliance.get("guide_source") or "journal_profile",
        details={
            "overall_status": compliance.get("overall_status"),
            "counts": compliance.get("counts"),
            "failed_rules": compliance.get("failed_rules"),
            "manual_review_required": compliance.get("manual_review_required"),
            "guide_verification_status": compliance.get("guide_verification_status"),
        },
    )


def _completeness_indicator(completeness: dict) -> dict:
    return _indicator(
        key="completeness",
        label="Completeness",
        available=True,
        value=completeness.get("score"),
        unit="score (0-100)",
        method="Required/optional component detection against the journal profile.",
        inputs="Parsed manuscript sections, figures, tables, equations.",
        interpretation="Missing required components lower the score and should be addressed.",
        evidence_type="computed",
        source="completeness",
        details={
            "missing_required": completeness.get("missing_required"),
            "missing_figure_captions": completeness.get("missing_figure_captions"),
            "missing_table_captions": completeness.get("missing_table_captions"),
            "word_count": completeness.get("word_count"),
            "word_limit": completeness.get("word_limit"),
        },
    )


def _similarity_indicator(scan: dict | None) -> dict:
    if scan is None:
        return _indicator(
            key="similarity",
            label="Similarity (latest scan)",
            available=False,
            method="Local corpus exact/near-exact matching.",
            inputs="No completed similarity scan found for this document.",
            interpretation="Run a similarity check to populate this indicator.",
            source="plagiarism_scan",
            details={"note": "Similarity is not a verdict and does not prove plagiarism."},
        )
    summary = (scan.get("report") or {}).get("summary") or {}
    return _indicator(
        key="similarity",
        label="Similarity (latest scan)",
        available=True,
        value=summary.get("overall_similarity"),
        unit="ratio (0-1)",
        method="Exact/near-exact lexical overlap against the configured local corpus.",
        inputs=f"Latest completed scan ({scan.get('scan_id')}).",
        interpretation="Overlap with identified sources only; verify every match. Not a plagiarism verdict.",
        evidence_type="computed",
        source=scan.get("provider") or "internal",
        details={
            "matched_words": summary.get("matched_words"),
            "total_words": summary.get("total_words"),
            "suspected_unattributed_words": summary.get("suspected_unattributed_words"),
            "source_count": summary.get("source_count"),
            "scan_id": scan.get("scan_id"),
            "scanned_at": scan.get("created_at"),
        },
    )


def _improvement_indicator(improvement: dict) -> dict:
    recommendations = improvement.get("recommendations") or []
    return _indicator(
        key="improvement",
        label="Improvement opportunities",
        available=True,
        value=len(recommendations),
        unit="open recommendations",
        method="Deterministic checks with optional AI enrichment.",
        inputs="Parsed manuscript, citations, and journal profile.",
        interpretation="Each recommendation is advisory and requires explicit acceptance.",
        evidence_type="computed",
        source="improvement_assessment",
        details={
            "priority_counts": improvement.get("priority_counts"),
            "ai_status": improvement.get("ai_status"),
        },
    )


def _prioritized_actions(compliance: dict, improvement: dict, readiness: dict) -> list[dict]:
    actions: list[dict] = []
    for rec in improvement.get("recommendations") or []:
        if rec.get("priority") in {"CRITICAL", "HIGH"}:
            actions.append(
                {
                    "source": "improvement",
                    "priority": rec.get("priority"),
                    "title": rec.get("issue"),
                    "detail": rec.get("suggestion"),
                    "section": rec.get("section"),
                    "requires_approval": True,
                }
            )
    for rule in compliance.get("rules") or []:
        if rule.get("status") == "failed":
            actions.append(
                {
                    "source": "compliance",
                    "priority": "HIGH",
                    "title": rule.get("description"),
                    "detail": rule.get("action"),
                    "section": rule.get("affected_section"),
                    "requires_approval": True,
                }
            )
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    actions.sort(key=lambda item: order.get(item.get("priority"), 9))
    return actions[:20]
