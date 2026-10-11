from __future__ import annotations

from pydantic import BaseModel, Field


class FormattingResult(BaseModel):
    document_id: str
    journal_id: str
    applied_rules: dict
    warnings: list[str] = Field(default_factory=list)
    warning_details: list[dict] = Field(default_factory=list)


def apply_formatting(document: dict, journal_rules: dict) -> FormattingResult:
    warning_details = []
    seen_warning_ids = set()

    def add_warning(rule_id: str, message: str, severity: str = "info", status: str = "manual_review", element_id: str = "document") -> None:
        warning_id = f"{journal_rules.get('journal_id', 'unknown')}:{rule_id}:{element_id}"
        if warning_id in seen_warning_ids:
            return
        seen_warning_ids.add(warning_id)
        warning_details.append({
            "id": warning_id,
            "rule_id": rule_id,
            "element_id": element_id,
            "severity": severity,
            "status": status,
            "message": message,
        })

    figures = document.get("figures") or []
    tables = document.get("tables") or []
    equations = document.get("equations") or []
    references = document.get("references") or []
    if document.get("title") or document.get("authors") or document.get("affiliations") or document.get("abstract"):
        add_warning("front_matter_typography_unapplied", "Title, author, affiliation, and abstract-specific typography is not fully applied; existing content is preserved.")
    if figures:
        add_warning("figure_placement_unapplied", "Figure placement and caption styling are not automatically changed; original inline images are preserved.")
        for index, figure in enumerate(figures, start=1):
            if not figure.get("caption"):
                element_id = f"{figure.get('id') or 'figure'}:{index}"
                add_warning("figure_caption_missing", f"{figure.get('id') or f'Figure {index}'} has no parsed caption; verify the original caption manually.", "medium", "verified_from_parsed_content", element_id)
    if tables:
        add_warning("table_styling_unapplied", "Existing table content is preserved, but journal-specific cell styling and caption placement are not applied.")
    if equations:
        add_warning("equation_layout_unapplied", "Equation XML is preserved in the source DOCX, but equation numbering and alignment are not changed.")
    if references:
        add_warning("reference_style_unapplied", "Citation and bibliography entries are preserved; in-text and reference-style conversion is not applied.")
    if document.get("sections"):
        add_warning("section_order_unapplied", "Configured section ordering is not rearranged; the manuscript's original order is preserved.")
    if journal_rules.get("page_numbering", {}).get("enabled"):
        add_warning("page_number_fields_unapplied", "Page-number fields are not inserted or rewritten by the current formatter.")
    header_footer = journal_rules.get("header_footer_rules", {})
    if header_footer.get("header") not in (None, "none") or header_footer.get("footer") not in (None, "none", "page-number"):
        add_warning("header_footer_unapplied", "Journal-specific headers or footers are not applied; existing content is preserved.")
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
        warnings=[warning["message"] for warning in warning_details],
        warning_details=warning_details,
    )
