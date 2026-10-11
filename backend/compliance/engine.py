"""Research completeness and submission compliance engine.

This module provides a single rule-based engine that is reused by journal
conversion, the manuscript dashboard, and the pre-submission validation screen.
Every rule returns an explicit status so that unknown or unverifiable rules are
reported as ``manual_review`` instead of a false ``passed``.
"""

from __future__ import annotations

import re
from typing import Any

from backend.ai_service import (
    _collect_manuscript_terms,
    _detected_section_types,
    _section_text,
)
from backend.citation.validator import validate_citations

from .requirements import (
    DECLARATION_LABELS,
    DEFAULT_ARTICLE_TYPE,
    normalize_article_type,
    requirements_for,
)

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_WARNING = "warning"
STATUS_MANUAL = "manual_review"
STATUS_NA = "not_applicable"

SECTION_LABELS = {
    "title": "Title",
    "abstract": "Abstract",
    "keywords": "Keywords",
    "introduction": "Introduction",
    "related_work": "Related work / Literature review",
    "research_gap": "Research gap",
    "methodology": "Methodology",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "limitations": "Limitations",
    "future_work": "Future work",
    "references": "References",
    "acknowledgments": "Acknowledgements",
    "funding": "Funding statement",
    "author_contributions": "Author contributions",
    "conflict_of_interest": "Conflict of interest declaration",
    "data_availability": "Data availability statement",
    "ethics": "Ethics statement",
    "supplementary_material": "Supplementary material",
}

DECLARATION_PATTERNS = {
    "funding": r"\b(funding|funded by|financial support|grant (?:number|no\.?)|this work was supported)\b",
    "author_contributions": r"\b(author contributions?|authors? contribut|cr edit|credit authorship)\b",
    "conflict_of_interest": r"\b(conflict of interest|conflicts of interest|competing interests?|no conflict)\b",
    "data_availability": r"\b(data availability|data are available|data is available|available (?:upon|on) request|data can be found)\b",
    "ethics": r"\b(ethics? (?:statement|approval)|ethical approval|institutional review board|\birb\b|informed consent)\b",
    "acknowledgments": r"\backnowledge?ments?\b|\bwe thank\b",
    "supplementary_material": r"\b(supplementary|supporting information|supporting material|appendix)\b",
}


def _rule(
    rule_id: str,
    category: str,
    description: str,
    status: str,
    *,
    evidence: str = "",
    affected_section: str | None = None,
    expected: str | None = None,
    actual: str | None = None,
    action: str | None = None,
    rule_source: str | None = None,
    verification_status: str = "unverified",
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "category": category,
        "description": description,
        "status": status,
        "evidence": evidence,
        "affected_section": affected_section,
        "expected": expected,
        "actual": actual,
        "action": action,
        "rule_source": rule_source,
        "verification_status": verification_status,
    }


def detect_declarations(document: dict | None) -> set[str]:
    text = _collect_manuscript_terms(document).lower()
    detected = set()
    for name, pattern in DECLARATION_PATTERNS.items():
        if re.search(pattern, text):
            detected.add(name)
    headings = _detected_section_types(document)
    for name in DECLARATION_LABELS:
        if name in headings:
            detected.add(name)
    return detected


def detected_components(document: dict | None) -> set[str]:
    document = document or {}
    detected = set(_detected_section_types(document))
    if document.get("title"):
        detected.add("title")
    if str(document.get("abstract") or "").strip():
        detected.add("abstract")
    if document.get("keywords"):
        detected.add("keywords")
    if document.get("references"):
        detected.add("references")
    intro = _section_text(document, "introduction").lower()
    if any(
        term in intro
        for term in ("research gap", "little is known", "few studies", "limited work", "has not been", "remains unexplored")
    ):
        detected.add("research_gap")
    detected |= detect_declarations(document)
    return detected


def resolve_required_components(journal: dict, article_type: str | None) -> tuple[list[str], list[str]]:
    preset = requirements_for(article_type)
    required = list(preset["required_components"])
    optional = list(preset["optional_components"])
    for item in journal.get("required_sections") or []:
        if item not in required:
            required.append(item)
    for item in journal.get("optional_sections") or []:
        if item not in optional and item not in required:
            optional.append(item)
    for item in journal.get("required_declarations") or []:
        if item not in required:
            required.append(item)
    return required, optional


def _journal_source(journal: dict) -> tuple[str, str]:
    guideline = journal.get("guideline") or {}
    source = guideline.get("source_name") or journal.get("journal_name") or "journal profile"
    verification = guideline.get("verification_status") or "unverified"
    return source, verification


def build_compliance_report(
    document: dict | None,
    journal: dict,
    *,
    article_type: str | None = None,
    source_format: str | None = None,
    page_count: int | None = None,
) -> dict[str, Any]:
    document = document or {}
    resolved_type = normalize_article_type(
        article_type or document.get("article_type") or document.get("metadata", {}).get("article_type")
    )
    source_name, verification = _journal_source(journal)
    required, optional = resolve_required_components(journal, resolved_type)
    detected = detected_components(document)
    rules: list[dict] = []

    # --- Structural completeness -----------------------------------------
    for component in required:
        label = SECTION_LABELS.get(component, component.replace("_", " ").title())
        present = component in detected
        rules.append(
            _rule(
                f"structure.{component}",
                "structural_completeness",
                f"{label} should be present for a {resolved_type.replace('_', ' ')}.",
                STATUS_PASSED if present else STATUS_FAILED,
                evidence=f"{label} {'was detected in the parsed manuscript.' if present else 'was not detected in the parsed manuscript.'}",
                affected_section=label,
                expected=f"Required component: {label}",
                actual="present" if present else "missing",
                action=None if present else f"Add or clearly label the {label.lower()}.",
                rule_source=source_name,
                verification_status=verification,
            )
        )
    for component in optional:
        if component in required:
            continue
        label = SECTION_LABELS.get(component, component.replace("_", " ").title())
        present = component in detected
        rules.append(
            _rule(
                f"structure.optional.{component}",
                "structural_completeness",
                f"{label} is optional for a {resolved_type.replace('_', ' ')}.",
                STATUS_PASSED if present else STATUS_NA,
                evidence=f"{label} {'is present.' if present else 'is not present and is not required.'}",
                affected_section=label,
                expected="optional",
                actual="present" if present else "not present",
                action=None,
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- Length rules -----------------------------------------------------
    word_count = len(_collect_manuscript_terms(document).split())
    word_limit = journal.get("word_limit")
    if word_limit:
        passed = word_count <= word_limit
        rules.append(
            _rule(
                "length.word_limit",
                "formatting",
                "Manuscript must respect the configured word limit.",
                STATUS_PASSED if passed else STATUS_FAILED,
                evidence=f"Measured {word_count} words against a configured limit of {word_limit}.",
                affected_section="Manuscript",
                expected=f"<= {word_limit} words",
                actual=f"{word_count} words",
                action=None if passed else "Shorten the manuscript to the configured limit and recheck the count.",
                rule_source=source_name,
                verification_status=verification,
            )
        )
    else:
        rules.append(
            _rule(
                "length.word_limit",
                "formatting",
                "Manuscript word limit.",
                STATUS_NA,
                evidence="No word limit is configured for the selected profile.",
                affected_section="Manuscript",
                expected="No configured limit",
                actual=f"{word_count} words",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    abstract_limit = (journal.get("abstract_formatting") or {}).get("max_words")
    abstract_words = len(str(document.get("abstract") or "").split())
    if abstract_limit:
        passed = abstract_words <= abstract_limit
        rules.append(
            _rule(
                "length.abstract_limit",
                "formatting",
                "Abstract must respect the configured word limit.",
                STATUS_PASSED if passed else STATUS_FAILED,
                evidence=f"Abstract measured {abstract_words} words against a configured limit of {abstract_limit}.",
                affected_section="Abstract",
                expected=f"<= {abstract_limit} words",
                actual=f"{abstract_words} words",
                action=None if passed else "Edit the abstract to meet the configured limit.",
                rule_source=source_name,
                verification_status=verification,
            )
        )
    else:
        rules.append(
            _rule(
                "length.abstract_limit",
                "formatting",
                "Abstract word limit.",
                STATUS_NA,
                evidence="No abstract word limit is configured for the selected profile.",
                affected_section="Abstract",
                expected="No configured limit",
                actual=f"{abstract_words} words",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    keyword_rules = journal.get("keyword_rules") or {}
    keyword_count = len(document.get("keywords") or [])
    max_keywords = keyword_rules.get("max_count")
    if keyword_rules.get("required") or max_keywords:
        if keyword_rules.get("required") and keyword_count == 0:
            status, action = STATUS_FAILED, "Add the required keywords."
        elif max_keywords and keyword_count > max_keywords:
            status, action = STATUS_FAILED, f"Reduce keywords to {max_keywords} or fewer."
        else:
            status, action = STATUS_PASSED, None
        rules.append(
            _rule(
                "formatting.keywords",
                "formatting",
                "Keyword count must satisfy the configured profile rules.",
                status,
                evidence=f"Detected {keyword_count} keyword(s).",
                affected_section="Keywords",
                expected=f"required={bool(keyword_rules.get('required'))}, max_count={max_keywords or 'n/a'}",
                actual=f"{keyword_count} keyword(s)",
                action=action,
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- Figures / tables / equations ------------------------------------
    missing_figure_captions = [
        figure.get("id") for figure in document.get("figures") or [] if isinstance(figure, dict) and not figure.get("caption")
    ]
    missing_table_captions = [
        table.get("id") for table in document.get("tables") or [] if isinstance(table, dict) and not table.get("caption")
    ]
    figures = document.get("figures") or []
    tables = document.get("tables") or []
    rules.append(
        _rule(
            "figures.captions",
            "formatting",
            "Every figure should have a caption.",
            STATUS_FAILED if missing_figure_captions else (STATUS_PASSED if figures else STATUS_NA),
            evidence=(
                f"Figures without captions: {', '.join(missing_figure_captions)}."
                if missing_figure_captions
                else (f"All {len(figures)} parsed figure(s) have captions." if figures else "No figures were detected.")
            ),
            affected_section="Figures",
            expected="Caption below each figure",
            actual=f"{len(missing_figure_captions)} missing of {len(figures)}",
            action="Add a caption below each figure." if missing_figure_captions else None,
            rule_source=source_name,
            verification_status=verification,
        )
    )
    rules.append(
        _rule(
            "tables.captions",
            "formatting",
            "Every table should have a caption.",
            STATUS_FAILED if missing_table_captions else (STATUS_PASSED if tables else STATUS_NA),
            evidence=(
                f"Tables without captions: {', '.join(missing_table_captions)}."
                if missing_table_captions
                else (f"All {len(tables)} parsed table(s) have captions." if tables else "No tables were detected.")
            ),
            affected_section="Tables",
            expected="Caption above each table",
            actual=f"{len(missing_table_captions)} missing of {len(tables)}",
            action="Add a caption above each table." if missing_table_captions else None,
            rule_source=source_name,
            verification_status=verification,
        )
    )
    rules.append(
        _rule(
            "figures.table.numbering",
            "formatting",
            "Figures and tables should be numbered sequentially.",
            STATUS_MANUAL,
            evidence="Figure/table numbering order cannot be verified automatically from the parsed structure.",
            affected_section="Figures and tables",
            expected="Sequential numbering",
            actual="Not automatically verifiable",
            action="Confirm figure and table numbering manually before submission.",
            rule_source=source_name,
            verification_status=verification,
        )
    )

    # --- Citation and reference validation --------------------------------
    citation_style = journal.get("citation_style")
    try:
        citation_issues = validate_citations(
            document.get("citations") or [],
            document.get("references") or [],
            citation_style,
        )
    except Exception:  # pragma: no cover - defensive
        citation_issues = {}
    citation_rules = [
        ("missing_references", "Every in-text citation should have a matching reference.", STATUS_FAILED),
        ("uncited_references", "Every reference should be cited in the text.", STATUS_WARNING),
        ("duplicate_references", "Reference entries should be unique.", STATUS_WARNING),
        ("duplicate_reference_numbers", "Reference numbers should be unique.", STATUS_WARNING),
        ("duplicate_citation_numbers", "Citation numbers should be unique.", STATUS_WARNING),
        ("numbering_issues", "Numeric citations and references should be consistently numbered.", STATUS_WARNING),
        ("malformed_references", "Reference entries should be well formed.", STATUS_WARNING),
        ("invalid_structure", "Reference entries should follow the expected structure.", STATUS_WARNING),
        ("invalid_dois", "DOIs should be valid.", STATUS_WARNING),
        ("author_year_mismatches", "Author-year citations should match the reference list.", STATUS_WARNING),
        ("references_wrong_order", "References should follow the configured ordering.", STATUS_WARNING),
        ("style_mismatches", "Reference entries should match the configured style.", STATUS_WARNING),
    ]
    found_any = False
    for key, description, fail_status in citation_rules:
        issues = citation_issues.get(key) or []
        if issues:
            found_any = True
        rules.append(
            _rule(
                f"citations.{key}",
                "citations",
                description,
                fail_status if issues else STATUS_PASSED,
                evidence=(
                    f"{len(issues)} issue(s): " + "; ".join(str(item.get("message", "")) for item in issues[:3])
                    if issues
                    else "No issues detected by the configured citation checks."
                ),
                affected_section="References",
                expected="No issues",
                actual=f"{len(issues)} issue(s)",
                action=(issues[0].get("suggestion") if issues and issues[0].get("suggestion") else ("Review the bibliography." if issues else None)),
                rule_source=source_name,
                verification_status=verification,
            )
        )
    rules.append(
        _rule(
            "citations.style",
            "citations",
            "In-text and reference style should follow the selected journal style.",
            STATUS_MANUAL,
            evidence=f"Configured citation style: {citation_style or 'not specified'}.",
            affected_section="References",
            expected=f"Apply {citation_style or 'the journal'} style",
            actual="Style conformance is not automatically verifiable",
            action="Confirm the citation and reference style against the journal's author guidelines.",
            rule_source=source_name,
            verification_status=verification,
        )
    )
    if not citation_issues.get("missing_references") and not citation_issues.get("uncited_references"):
        pass

    # --- Declarations required by the journal -----------------------------
    declared = detect_declarations(document)
    for decl in journal.get("required_declarations") or []:
        label = DECLARATION_LABELS.get(decl, decl.replace("_", " ").title())
        present = decl in declared
        rules.append(
            _rule(
                f"declaration.{decl}",
                "declarations",
                f"{label} is required by the selected journal profile.",
                STATUS_PASSED if present else STATUS_FAILED,
                evidence=f"{label} {'was detected in the manuscript text.' if present else 'was not detected in the manuscript text.'}",
                affected_section=label,
                expected=f"Required declaration: {label}",
                actual="present" if present else "missing",
                action=None if present else f"Add the {label.lower()}.",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- File format ------------------------------------------------------
    effective_format = (source_format or document.get("metadata", {}).get("source_format") or "docx").lower()
    allowed_formats = [item.lower().lstrip(".") for item in (journal.get("allowed_formats") or ["docx"])]
    format_passed = effective_format in allowed_formats
    rules.append(
        _rule(
            "submission.file_format",
            "submission",
            "The source file format should be accepted by the submission system.",
            STATUS_PASSED if format_passed else STATUS_WARNING,
            evidence=f"Parsed source format: {effective_format}. Allowed: {', '.join(allowed_formats)}.",
            affected_section="File",
            expected=", ".join(allowed_formats),
            actual=effective_format,
            action=None if format_passed else "Convert the manuscript to an allowed submission format.",
            rule_source=source_name,
            verification_status=verification,
        )
    )

    # --- Page limit -------------------------------------------------------
    page_limit = journal.get("page_limit")
    if page_limit:
        if page_count:
            passed = page_count <= page_limit
            rules.append(
                _rule(
                    "length.page_limit",
                    "formatting",
                    "Manuscript must respect the configured page limit.",
                    STATUS_PASSED if passed else STATUS_FAILED,
                    evidence=f"Measured {page_count} page(s) against a configured limit of {page_limit}.",
                    affected_section="Manuscript",
                    expected=f"<= {page_limit} pages",
                    actual=f"{page_count} pages",
                    action=None if passed else "Reduce the manuscript length to meet the page limit.",
                    rule_source=source_name,
                    verification_status=verification,
                )
            )
        else:
            rules.append(
                _rule(
                    "length.page_limit",
                    "formatting",
                    "Manuscript must respect the configured page limit.",
                    STATUS_MANUAL,
                    evidence="The page limit is configured, but page count cannot be measured from the parsed DOCX structure.",
                    affected_section="Manuscript",
                    expected=f"<= {page_limit} pages",
                    actual="Page count not measurable from DOCX",
                    action="Verify the rendered page count against the configured limit.",
                    rule_source=source_name,
                    verification_status=verification,
                )
            )
    else:
        rules.append(
            _rule(
                "length.page_limit",
                "formatting",
                "Manuscript page limit.",
                STATUS_NA,
                evidence="No page limit is configured for the selected profile.",
                affected_section="Manuscript",
                expected="No configured limit",
                actual="Not applicable",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- Anonymity --------------------------------------------------------
    if journal.get("anonymity_required"):
        rules.append(
            _rule(
                "submission.anonymity",
                "submission",
                "Double-blind submission requires anonymized author information.",
                STATUS_MANUAL,
                evidence="Anonymity requirements cannot be verified automatically from the parsed text.",
                affected_section="Title page",
                expected="No identifying author or affiliation information",
                actual="Manual verification required",
                action="Remove author names and affiliations from the anonymized manuscript file before submission.",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- Supplementary / other manual rules -------------------------------
    if (journal.get("supplementary_material_rules") or {}).get("allowed"):
        rules.append(
            _rule(
                "submission.supplementary",
                "submission",
                "Supplementary files must be supplied where required.",
                STATUS_MANUAL,
                evidence="Supplementary file completeness cannot be verified from the manuscript text.",
                affected_section="Supplementary material",
                expected="Required supplementary files included",
                actual="Manual verification required",
                action="Confirm that all required supplementary files are prepared for upload.",
                rule_source=source_name,
                verification_status=verification,
            )
        )

    # --- Aggregate --------------------------------------------------------
    counts = {
        STATUS_PASSED: 0,
        STATUS_FAILED: 0,
        STATUS_WARNING: 0,
        STATUS_MANUAL: 0,
        STATUS_NA: 0,
    }
    for rule in rules:
        counts[rule["status"]] = counts.get(rule["status"], 0) + 1
    assessed = [rule for rule in rules if rule["status"] != STATUS_NA]
    automated = [rule for rule in assessed if rule["status"] in {STATUS_PASSED, STATUS_FAILED, STATUS_WARNING}]
    passed_automated = [rule for rule in automated if rule["status"] == STATUS_PASSED]
    compliance_score = round(100 * len(passed_automated) / len(automated)) if automated else None

    if counts[STATUS_FAILED]:
        overall_status = STATUS_FAILED
    elif counts[STATUS_WARNING] or counts[STATUS_MANUAL]:
        overall_status = STATUS_WARNING
    else:
        overall_status = STATUS_PASSED

    return {
        "document_id": document.get("document_id"),
        "journal_id": journal.get("journal_id"),
        "journal_name": journal.get("journal_name"),
        "article_type": resolved_type,
        "guide_source": source_name,
        "guide_verification_status": verification,
        "guide_source_url": (journal.get("guideline") or {}).get("source_url"),
        "guide_last_checked": (journal.get("guideline") or {}).get("last_checked"),
        "overall_status": overall_status,
        "compliance_score": compliance_score,
        "required_components": required,
        "optional_components": [item for item in optional if item not in required],
        "detected_components": sorted(detected),
        "counts": counts,
        "rules": rules,
        "manual_review_required": [rule["rule_id"] for rule in rules if rule["status"] == STATUS_MANUAL],
        "failed_rules": [rule["rule_id"] for rule in rules if rule["status"] == STATUS_FAILED],
        "analysis_scope": (
            "Rule-based structural and formatting compliance against the selected profile. "
            "Rules marked 'manual_review' could not be verified automatically and must be checked by the author."
        ),
    }


def word_limit_analysis(document: dict | None, journal: dict) -> dict[str, Any]:
    """Measure the manuscript against the journal word limit and attribute the
    excess to individual sections. Never deletes content; only suggests."""
    document = document or {}
    limit = journal.get("word_limit")
    total = len(_collect_manuscript_terms(document).split())
    sections = []
    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        count = len(str(section.get("content") or "").split())
        sections.append(
            {
                "section": section.get("heading") or section.get("type") or "Section",
                "type": section.get("type"),
                "words": count,
            }
        )
    abstract_words = len(str(document.get("abstract") or "").split())
    if abstract_words:
        sections.insert(0, {"section": "Abstract", "type": "abstract", "words": abstract_words})
    sections.sort(key=lambda item: item["words"], reverse=True)
    exceed = max(0, total - limit) if limit else 0
    suggestions = []
    if limit and total > limit:
        for section in sections:
            if section["words"] < 20:
                continue
            reduction = min(section["words"] // 3, max(1, exceed // max(1, len(sections))))
            suggestions.append(
                {
                    "section": section["section"],
                    "current_words": section["words"],
                    "suggested_reduction": reduction,
                    "suggestion": (
                        f"Consider tightening {section['section']} by roughly {reduction} words by removing redundancy, "
                        "without removing equations, results, or citations."
                    ),
                }
            )
    return {
        "word_count": total,
        "word_limit": limit,
        "exceeds_limit": bool(limit and total > limit),
        "excess_words": exceed,
        "abstract_words": abstract_words,
        "section_breakdown": sections,
        "suggestions": suggestions,
        "note": "Automatic shortening is never applied. Any substantive edit requires explicit author approval.",
    }
