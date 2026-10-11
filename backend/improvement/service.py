"""AI research improvement assistant.

This module produces actionable, section-specific improvement recommendations and
optional suggested revisions. Deterministic, evidence-based checks run always;
the optional external AI provider only enriches them. Nothing is ever applied to
the manuscript without explicit user acceptance.
"""

from __future__ import annotations

import re
from typing import Any

from backend import ai_service
from backend.ai_provider import LocalMockProvider, get_ai_provider

PRIORITY_ORDER = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}

# Dimensions from the product specification, mapped to how they are evidenced.
DIMENSION_LABELS = {
    "problem_clarity": "Research problem clarity",
    "objectives_motivation": "Research objectives and motivation",
    "literature_review": "Literature review and related work",
    "research_gap_novelty": "Research gap and claimed novelty",
    "technical_contribution": "Technical contribution",
    "methodology_reproducibility": "Methodology and reproducibility",
    "experimental_design": "Experimental design and validation",
    "results_discussion": "Results and discussion",
    "statistical_evidence": "Statistical evidence, baselines and comparisons",
    "limitations_future_work": "Limitations and future work",
    "language_clarity": "Academic language, clarity and structure",
    "citation_completeness": "Citation and reference completeness",
    "submission_readiness": "Overall journal and submission readiness",
}

REVISION_GOALS = {
    "grammar": "Improve grammar and academic language without changing meaning.",
    "clarity": "Improve clarity and readability without changing meaning.",
    "concise": "Make the text more concise without removing evidence, citations, or results.",
    "transition": "Improve the paragraph transition without changing meaning.",
    "methodology": "Explain the methodology more clearly without inventing details.",
    "contribution": "Explain the technical contribution more clearly without overstating results.",
    "abstract": "Improve the abstract while preserving all reported claims and numbers.",
    "conclusion": "Improve the conclusion while preserving all reported claims.",
    "limitations": "Improve the limitations statement without inventing limitations.",
}

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_CITATION_RE = re.compile(
    r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]"
    r"|\b[A-Z][A-Za-z-]+(?:\s+et al\.)?\s*\(\s*\d{4}[a-z]?\s*\)"
    r"|\bdoi:\s*10\.\d{4,9}/\S+"
    r"|10\.\d{4,9}/\S+",
    re.IGNORECASE,
)


def _confidence(evidence_type: str, priority: str) -> str:
    if evidence_type == "factual":
        return "high"
    return {"CRITICAL": "medium", "HIGH": "medium", "MEDIUM": "low", "LOW": "low"}.get(priority, "low")


def _recommendation(
    *,
    section: str,
    issue: str,
    why_it_matters: str,
    evidence: str,
    suggestion: str,
    priority: str,
    evidence_type: str,
    text_location: str | None = None,
    original: str | None = None,
) -> dict[str, Any]:
    priority = priority if priority in PRIORITY_ORDER else "MEDIUM"
    return {
        "id": None,
        "section": section,
        "issue": issue,
        "why_it_matters": why_it_matters,
        "evidence": evidence,
        "suggestion": suggestion,
        "priority": priority,
        "confidence": _confidence(evidence_type, priority),
        "evidence_type": evidence_type,
        "text_location": text_location,
        "original": original,
        "requires_approval": True,
    }


def _structural_recommendations(document_id: str, analysis: dict, journal_id: str | None) -> list[dict]:
    completeness = ai_service.analyze_completeness(document_id, analysis, journal_id)
    recommendations: list[dict] = []
    for missing in completeness["missing_required"]:
        label = missing.replace("_", " ")
        recommendations.append(
            _recommendation(
                section=missing,
                issue=f"Required component not detected: {label}.",
                why_it_matters="The selected journal profile lists this component as required for the chosen article type.",
                evidence=f"The parsed manuscript did not contain a '{label}' section heading or content.",
                suggestion=f"Add or clearly label the {label} section to match the selected profile.",
                priority="HIGH",
                evidence_type="factual",
            )
        )
    for missing in completeness["missing_figure_captions"]:
        recommendations.append(
            _recommendation(
                section="Figures",
                issue=f"{missing} has no parsed caption.",
                why_it_matters="Reviewers expect every figure to be numbered and described by a caption.",
                evidence=f"Figure metadata for {missing} contained no caption text.",
                suggestion="Add a caption below the figure that describes what it shows.",
                priority="HIGH",
                evidence_type="factual",
            )
        )
    for missing in completeness["missing_table_captions"]:
        recommendations.append(
            _recommendation(
                section="Tables",
                issue=f"{missing} has no parsed caption.",
                why_it_matters="Tables should be numbered and titled so reviewers can interpret them.",
                evidence=f"Table metadata for {missing} contained no caption text.",
                suggestion="Add a caption above the table that describes its contents.",
                priority="HIGH",
                evidence_type="factual",
            )
        )
    for equation in completeness["unnumbered_equations"]:
        recommendations.append(
            _recommendation(
                section="Equations",
                issue=f"{equation} has no visible number.",
                why_it_matters="Displayed equations are normally numbered so they can be referenced.",
                evidence=f"Parsed equation {equation} did not include a number.",
                suggestion="Number displayed equations according to the selected journal profile.",
                priority="MEDIUM",
                evidence_type="factual",
            )
        )
    if completeness["word_limit_exceeded"]:
        recommendations.append(
            _recommendation(
                section="Manuscript",
                issue=f"Manuscript exceeds the configured word limit ({completeness['word_count']} / {completeness['word_limit']}).",
                why_it_matters="Exceeding the limit can cause desk rejection before review.",
                evidence="The selected journal profile has a configured word limit and the measured count exceeds it.",
                suggestion="Shorten the manuscript without removing equations, results, or citations, then recheck the count.",
                priority="HIGH",
                evidence_type="factual",
            )
        )
    if completeness["abstract_limit_exceeded"]:
        recommendations.append(
            _recommendation(
                section="Abstract",
                issue=f"Abstract exceeds the configured limit ({completeness['abstract_word_count']} / {completeness['abstract_word_limit']}).",
                why_it_matters="Abstracts are often screened against a strict word limit.",
                evidence="The selected journal profile has an abstract limit and the measured count exceeds it.",
                suggestion="Edit the abstract to meet the configured limit while keeping all claims.",
                priority="MEDIUM",
                evidence_type="factual",
            )
        )
    return recommendations


def _content_recommendations(document_id: str, analysis: dict, journal_id: str | None) -> list[dict]:
    method = ai_service.analyze_methodology(document_id, analysis)
    writing = ai_service.analyze_writing(document_id, analysis)
    recommendations: list[dict] = []

    for missing in method["missing_information"][:6]:
        recommendations.append(
            _recommendation(
                section="methodology",
                issue=f"The methodology does not clearly identify {missing.lower()}.",
                why_it_matters="Reproducibility depends on clearly reporting the setup, data, and evaluation.",
                evidence=f"Deterministic methodology checks did not find text describing {missing.lower()}.",
                suggestion=f"Report {missing.lower()} explicitly in the methodology where it applies.",
                priority="MEDIUM",
                evidence_type="factual",
            )
        )
    intro = ai_service._section_text(analysis, "introduction").lower()
    if intro and not any(term in intro for term in ("research gap", "little is known", "few studies", "limited work", "has not been")):
        recommendations.append(
            _recommendation(
                section="introduction",
                issue="No explicit research-gap statement was detected in the introduction.",
                why_it_matters="A clear gap statement frames the contribution and why the work is needed.",
                evidence="The introduction text did not contain a recognizable gap phrasing.",
                suggestion="State the research gap and distinguish it from cited prior work.",
                priority="MEDIUM",
                evidence_type="ai_suggestion",
            )
        )
    for finding in writing["sentence_findings"][:5]:
        recommendations.append(
            _recommendation(
                section="writing",
                issue=finding["problem"],
                why_it_matters=finding["reason"],
                evidence="The sentence was flagged by deterministic writing checks.",
                suggestion=finding["suggested_improvement"],
                priority="LOW",
                evidence_type="factual",
                original=finding["original"],
            )
        )
    return recommendations


def _citation_recommendations(document_id: str, analysis: dict, journal_id: str | None) -> list[dict]:
    from backend.citation.validator import validate_citations
    from backend.journal.rules import get_journal_rules

    citation_style = get_journal_rules((journal_id or "nature").lower()).get("citation_style")
    issues = validate_citations(analysis.get("citations") or [], analysis.get("references") or [], citation_style)
    recommendations: list[dict] = []
    for group, items in issues.items():
        severity = "CRITICAL" if group == "missing_references" else "HIGH"
        for item in items:
            recommendations.append(
                _recommendation(
                    section="References",
                    issue=item.get("message") or f"Citation issue: {group.replace('_', ' ')}.",
                    why_it_matters="Consistent citation and reference linking is required for review.",
                    evidence=f"The citation validator ({group.replace('_', ' ')}) reported this issue.",
                    suggestion=item.get("suggestion") or "Review the bibliography against the selected journal's reference requirements.",
                    priority=severity if group == "missing_references" else "MEDIUM",
                    evidence_type="factual",
                    text_location=item.get("citation"),
                )
            )
    return recommendations


def assess_manuscript(document_id: str, analysis: dict | None = None, journal_id: str | None = None) -> dict[str, Any]:
    """Return a structured, section-specific improvement assessment."""
    document = analysis or {}
    recommendations = [
        *_structural_recommendations(document_id, document, journal_id),
        *_citation_recommendations(document_id, document, journal_id),
        *_content_recommendations(document_id, document, journal_id),
    ]
    for index, item in enumerate(recommendations, start=1):
        item["id"] = f"rec-{index}"

    provider = get_ai_provider()
    configured = not isinstance(provider, LocalMockProvider)

    priorities = {level: sum(1 for item in recommendations if item["priority"] == level) for level in PRIORITY_ORDER}
    dimensions = _dimension_summary(document_id, document, journal_id, recommendations)

    return {
        "document_id": document_id,
        "journal_id": (journal_id or "nature").lower(),
        "recommendations": recommendations,
        "priority_counts": priorities,
        "dimensions": dimensions,
        "ai_status": "enhanced" if configured else "limited_analysis",
        "ai_provider": provider.name,
        "ai_message": (
            "External structured analysis is enabled; suggestions are AI-generated and must be verified."
            if configured
            else "No AI provider is configured; only deterministic, evidence-based checks are shown."
        ),
        "analysis_scope": (
            "Recommendations combine deterministic checks with optional AI suggestions. "
            "They do not verify experiments, novelty, or scientific correctness."
        ),
    }


def _dimension_summary(document_id: str, analysis: dict, journal_id: str | None, recommendations: list[dict]) -> list[dict]:
    completeness = ai_service.analyze_completeness(document_id, analysis, journal_id)
    method = ai_service.analyze_methodology(document_id, analysis)
    contribution = ai_service.analyze_contribution(document_id, analysis)
    novelty = ai_service.analyze_novelty(document_id, analysis)
    writing = ai_service.analyze_writing(document_id, analysis)
    sections = {item.lower() for item in (completeness.get("detected_sections") or [])}

    def count_by_section(*names: str) -> int:
        wanted = set(names)
        return sum(1 for item in recommendations if str(item["section"]).lower() in wanted)

    return [
        {"key": "problem_clarity", "available": bool(analysis.get("abstract") or analysis.get("sections")), "detail": "Detected from the abstract and introduction evidence."},
        {"key": "objectives_motivation", "available": bool(analysis.get("abstract")), "detail": "Motivation is inferred from the abstract and introduction."},
        {"key": "literature_review", "available": "related_work" in sections or "literature review" in sections, "detail": "Presence of a related-work or literature-review section."},
        {"key": "research_gap_novelty", "available": True, "detail": f"Novelty framing score: {novelty.get('novelty_score')}/100 (internal evidence only)."},
        {"key": "technical_contribution", "available": True, "detail": f"Contribution evidence score: {contribution.get('technical_contribution_score')}/100."},
        {"key": "methodology_reproducibility", "available": True, "detail": f"Methodology evidence score: {method.get('score')}/100; {len(method.get('missing_information') or [])} items not explicit."},
        {"key": "experimental_design", "available": "results" in sections, "detail": "Detected a results section for evaluation evidence."},
        {"key": "results_discussion", "available": "results" in sections or "discussion" in sections, "detail": "Presence of results/discussion sections."},
        {"key": "statistical_evidence", "available": True, "detail": f"{count_by_section('methodology')} methodology recommendations relate to evaluation evidence."},
        {"key": "limitations_future_work", "available": "limitations" in sections or "future work" in sections, "detail": "Presence of limitations/future-work sections."},
        {"key": "language_clarity", "available": True, "detail": f"{len(writing.get('issues') or [])} rule-based writing issues detected."},
        {"key": "citation_completeness", "available": True, "detail": f"{count_by_section('references')} citation/reference recommendations."},
        {"key": "submission_readiness", "available": True, "detail": "Overall readiness is shown on the analytics dashboard."},
    ]


def _validate_revision(original: str, revised: str) -> tuple[bool, str]:
    if not revised or not revised.strip():
        return False, "The provider returned empty text."
    original_numbers = set(_NUMBER_RE.findall(original))
    revised_numbers = set(_NUMBER_RE.findall(revised))
    invented = revised_numbers - original_numbers
    if invented:
        return False, f"Revision introduced numbers not present in the original text: {', '.join(sorted(invented))}."
    original_citations = set(_CITATION_RE.findall(original))
    revised_citations = set(_CITATION_RE.findall(revised))
    invented_citations = revised_citations - original_citations
    if invented_citations:
        return False, "Revision introduced citations not present in the original text."
    return True, "ok"


def generate_revisions(document_id: str, analysis: dict | None = None, targets: list[dict] | None = None) -> dict[str, Any]:
    """Produce original/revised pairs for user review.

    Without a configured AI provider, no rewriting is fabricated: the deterministic
    writing findings are returned as guidance instead.
    """
    document = analysis or {}
    provider = get_ai_provider()
    if isinstance(provider, LocalMockProvider):
        writing = ai_service.analyze_writing(document_id, document)
        return {
            "document_id": document_id,
            "revisions": [],
            "deterministic_findings": writing.get("sentence_findings") or [],
            "ai_status": "limited_analysis",
            "ai_provider": provider.name,
            "message": (
                "No AI provider is configured, so automatic rewrites are disabled. "
                "The deterministic writing findings below are provided as guidance and require your own edits."
            ),
            "requires_approval": True,
            "source_modified": False,
        }

    revisions: list[dict] = []
    for target in targets or []:
        original = (target.get("original") or "").strip()
        goal = (target.get("goal") or "clarity").strip().lower()
        if not original:
            continue
        instruction = REVISION_GOALS.get(goal, REVISION_GOALS["clarity"])
        try:
            result = provider.generate_json(
                "revision",
                {"instruction": instruction, "original_text": original},
                ["revised_text"],
            )
            revised = str(result.get("revised_text") or "").strip()
        except Exception as exc:  # provider failure must not crash the request
            revisions.append({
                "section": target.get("section"),
                "goal": goal,
                "original": original,
                "revised": None,
                "status": "provider_error",
                "detail": f"The AI provider could not produce a revision: {exc}",
                "requires_approval": True,
            })
            continue
        valid, reason = _validate_revision(original, revised)
        revisions.append({
            "section": target.get("section"),
            "goal": goal,
            "original": original,
            "revised": revised if valid else None,
            "status": "proposed" if valid else "rejected_unsafe",
            "detail": "Proposed revision; review and accept or reject." if valid else reason,
            "requires_approval": True,
        })
    return {
        "document_id": document_id,
        "revisions": revisions,
        "ai_status": "enhanced",
        "ai_provider": provider.name,
        "message": "AI-generated revisions are advisory. Accept only edits that preserve your meaning.",
        "requires_approval": True,
        "source_modified": False,
    }


def recommend_experiments(document_id: str, analysis: dict | None = None) -> dict[str, Any]:
    """Recommend what should be tested next without fabricating outcomes."""
    document = analysis or {}
    method = ai_service.analyze_methodology(document_id, document)
    suggestions = []
    for missing in method.get("missing_information") or []:
        suggestions.append({
            "area": missing,
            "recommendation": (
                f"If {missing.lower()} applies to this study, design an experiment, evaluation, or ablation that "
                "reports it. Do not state results until they are measured."
            ),
            "evidence": f"Deterministic methodology checks did not find {missing.lower()}.",
            "priority": "MEDIUM",
        })
    return {
        "document_id": document_id,
        "suggestions": suggestions,
        "disclaimer": "These are recommendations for additional evaluation. No experimental results are generated or assumed.",
    }
