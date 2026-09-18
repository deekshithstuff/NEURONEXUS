from __future__ import annotations

from .database import load_journal_rules


def get_available_journals() -> list[dict]:
    return load_journal_rules()


def get_journal_rules(journal_id: str) -> dict:
    for rule in load_journal_rules():
        if rule["journal_id"] == journal_id:
            return rule
    raise ValueError(f"Unsupported journal: {journal_id}")
