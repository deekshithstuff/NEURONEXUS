from __future__ import annotations


def format_figure_rules(journal_rules: dict) -> dict:
    return journal_rules.get("figure_rules", {})


def apply_figure_rules(figures: list[dict], rules: dict) -> list[dict]:
    """Apply journal-specific figure formatting without altering scientific content."""
    for figure in figures:
        figure.setdefault("formatting", {})
        figure["formatting"]["position"] = rules.get("figure_rules", {}).get("position", "float")
        figure["formatting"]["caption_style"] = rules.get("figure_rules", {}).get("caption_style", "Figure")
    return figures
