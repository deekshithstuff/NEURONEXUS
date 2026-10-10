from __future__ import annotations

from .database import load_journal_rules


def get_available_journals() -> list[dict]:
    journals = []
    seen_ids = set()
    for journal in load_journal_rules():
        journal_id = journal.get("journal_id")
        if not journal_id or journal_id in seen_ids:
            continue
        seen_ids.add(journal_id)
        journals.append(journal)
    return journals


def get_journal_rules(journal_id: str) -> dict:
    for rule in get_available_journals():
        if rule["journal_id"] == journal_id:
            return rule
    raise ValueError(f"Unsupported journal: {journal_id}")
