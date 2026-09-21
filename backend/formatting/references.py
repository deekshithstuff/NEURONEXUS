def format_reference_rules(journal_rules: dict) -> dict:
    return {
        "citation_style": journal_rules.get("citation_style"),
        "reference_style": journal_rules.get("reference_style"),
    }
