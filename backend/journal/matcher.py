from __future__ import annotations

from backend.ai_service import generate_journal_match

from .rules import get_journal_rules


def match_journal(document_metadata: dict) -> dict:
    if not isinstance(document_metadata, dict):
        return {"journal_id": None, "match_status": "insufficient_content"}

    match = generate_journal_match("upload-journal-selection", document_metadata)
    if match["match_status"] != "evaluated":
        return {"journal_id": None, "match_status": match["match_status"]}
    best = next(
        (item for item in match["ranked_journals"] if (item.get("scope_match") or 0) > 0),
        None,
    )
    if best is None:
        return {"journal_id": None, "match_status": "no_scope_evidence"}
    return {
        **get_journal_rules(best["journal_id"]),
        "match_score": best["scope_match"],
        "match_status": "evaluated",
    }
