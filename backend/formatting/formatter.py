from __future__ import annotations

from pydantic import BaseModel


class FormattingResult(BaseModel):
    document_id: str
    journal_id: str
    applied_rules: dict
    warnings: list[str] = []


def apply_formatting(document: dict, journal_rules: dict) -> FormattingResult:
    return FormattingResult(
        document_id=document.get("document_id", "unknown"),
        journal_id=journal_rules.get("journal_id", "nature"),
        applied_rules={
            "page_size": journal_rules.get("page_size"),
            "margins": journal_rules.get("margins"),
            "columns": journal_rules.get("columns"),
            "font": journal_rules.get("font"),
            "font_size": journal_rules.get("font_size"),
            "heading_styles": journal_rules.get("heading_styles"),
            "figure_rules": journal_rules.get("figure_rules"),
            "table_rules": journal_rules.get("table_rules"),
            "equation_rules": journal_rules.get("equation_rules"),
        },
        warnings=[],
    )
