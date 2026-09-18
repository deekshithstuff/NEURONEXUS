from __future__ import annotations

from .rules import get_available_journals, get_journal_rules


def match_journal(document_metadata: dict) -> dict:
    title = (document_metadata.get("title") or "").lower()
    for journal in get_available_journals():
        if "ieee" in title and journal["journal_id"] == "ieee":
            return journal
        if "nature" in title and journal["journal_id"] == "nature":
            return journal
    return get_journal_rules("nature")
