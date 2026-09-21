from __future__ import annotations


def format_equation_rules(journal_rules: dict) -> dict:
    return journal_rules.get("equation_rules", {})


def apply_equation_rules(equations: list[dict], rules: dict) -> list[dict]:
    """Apply journal-specific equation handling while preserving the original XML."""
    preserve = rules.get("equation_rules", {}).get("preserve_xml", True)
    for equation in equations:
        equation.setdefault("formatting", {})
        equation["formatting"]["preserve_xml"] = preserve
        equation["formatting"]["journal_rule"] = rules.get("journal_id", "nature")
    return equations
