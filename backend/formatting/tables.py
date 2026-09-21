from __future__ import annotations


def format_table_rules(journal_rules: dict) -> dict:
    return journal_rules.get("table_rules", {})


def apply_table_rules(tables: list[dict], rules: dict) -> list[dict]:
    """Apply journal-specific table formatting without altering scientific content."""
    for table in tables:
        table.setdefault("formatting", {})
        table["formatting"]["position"] = rules.get("table_rules", {}).get("position", "top")
        table["formatting"]["caption_style"] = rules.get("table_rules", {}).get("caption_style", "Table")
    return tables
