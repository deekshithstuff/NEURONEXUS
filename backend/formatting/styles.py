from __future__ import annotations


def build_heading_styles(journal_rules: dict) -> dict:
    return journal_rules.get("heading_styles", {})
