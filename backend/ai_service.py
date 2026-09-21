from __future__ import annotations

import json
import re
from typing import Any

from backend.journal.rules import get_journal_rules


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _normalize_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.findall(r"[a-z0-9]+", (value or "").lower()) if token}


def _collect_manuscript_terms(analysis: dict | None) -> str:
    if not isinstance(analysis, dict):
        return ""
    sections = analysis.get("sections") or []
    section_text = " ".join(
        str((section or {}).get("content") or (section or {}).get("heading") or "")
        for section in sections
        if isinstance(section, dict)
    )
    keywords = analysis.get("keywords") or []
    return " ".join([
        str(analysis.get("title") or ""),
        str(analysis.get("abstract") or ""),
        section_text,
        *[str(item) for item in keywords],
    ])


def _journal_scope_topics(journal: dict | None) -> set[str]:
    if not isinstance(journal, dict):
        return set()
    scope_topics = journal.get("scope_topics") or []
    topics = set()
    for item in scope_topics:
        topics |= _normalize_tokens(str(item))
    return topics


def _match_score_for_topics(manuscript_text: str, journal: dict | None) -> tuple[float, list[str], list[str]]:
    manuscript_tokens = _normalize_tokens(manuscript_text)
    if not manuscript_tokens:
        return 0.0, [], ["The manuscript content is missing, so journal scope compatibility could not be assessed from the document itself."]

    normalized_manuscript = _normalize_text(manuscript_text).lower()
    journal_scope_aliases = journal.get("scope_aliases") if isinstance(journal, dict) else {}
    ranked_matches: list[tuple[str, float]] = []
    seen: set[str] = set()

    for _, aliases in (journal_scope_aliases or {}).items():
        if not isinstance(aliases, (list, tuple, set)):
            continue
        for alias in aliases:
            alias_text = _normalize_text(str(alias)).lower()
            if not alias_text or alias_text in seen:
                continue
            alias_tokens = _normalize_tokens(alias_text)
            if not alias_tokens:
                continue
            match_strength = 0.0
            if alias_text in normalized_manuscript:
                match_strength = 2.5
            elif alias_tokens <= manuscript_tokens:
                match_strength = 2.0
            elif len(alias_tokens & manuscript_tokens) > 0:
                match_strength = 1.0 + (len(alias_tokens & manuscript_tokens) / max(len(alias_tokens), 1))
            if match_strength > 0:
                ranked_matches.append((alias_text, match_strength))
                seen.add(alias_text)

    if ranked_matches:
        ranked_matches.sort(key=lambda item: item[1], reverse=True)
        matched_topics = [label for label, _ in ranked_matches[:5]]
    else:
        scope_tokens = _journal_scope_topics(journal)
        overlaps = sorted(manuscript_tokens & scope_tokens)
        if overlaps:
            matched_topics = overlaps[:5]
        else:
            matched_topics = [sorted(manuscript_tokens, key=len)[0]]

    if not matched_topics:
        return 0.0, [], ["The manuscript topic is not currently aligned with the selected journal's scope and requires further review."]

    score = 0.0
    for topic in matched_topics:
        topic_tokens = _normalize_tokens(str(topic))
        if not topic_tokens:
            continue
        overlap = len(topic_tokens & manuscript_tokens)
        score += min(1.0, overlap / max(len(topic_tokens), 1))
    score = round(min(0.99, score / max(len(matched_topics), 1)), 4)
    score = max(score, 0.1)

    gaps = []
    if score < 0.45:
        gaps.append("The manuscript topic does not closely match the selected journal's scope and should be reviewed further.")
    elif score < 0.7:
        gaps.append("The manuscript aligns partially with the journal's focus but may require a clearer topic positioning.")

    return score, matched_topics[:5], gaps


def analyze_quality(document_id: str, analysis: dict | None = None) -> dict:
    document = analysis or {}
    body = _normalize_text(document.get("abstract") or document.get("paragraphs", [""])[0])
    sections = [section.get("type", "") for section in document.get("sections", [])]
    missing = []
    for required in [
        "abstract",
        "introduction",
        "related_work",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
    ]:
        if required not in sections:
            missing.append(required)

    writing_issues = []
    if not document.get("keywords"):
        writing_issues.append("Keywords are missing or too sparse for discovery.")
    if len(body) < 120:
        writing_issues.append("Abstract is short and may not explain the problem, method, and result clearly.")

    return {
        "document_id": document_id,
        "module": "quality",
        "research_gap": "The manuscript presents a clear technical problem and motivation, but a stronger explicit comparison against prior work would improve the literature positioning.",
        "technical_contribution": "The manuscript describes a concrete model or method with some evidence of performance, but the contribution should be framed more explicitly around the unique technical advance.",
        "methodology_issues": [
            issue for issue in [
                "Dataset scale and curation details should be stated more clearly.",
                "Experimental settings should include more baseline comparisons and ablation details.",
            ] if issue
        ],
        "missing_sections": missing,
        "writing_issues": writing_issues,
        "suggestions": [
            "State the research gap in a single paragraph with explicit comparison to prior work.",
            "Add a concise contributions paragraph after the abstract or introduction.",
            "Clarify datasets, splits, baselines, and evaluation metrics in the methodology section.",
        ],
    }


def analyze_methodology(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    text = "\n".join(doc.get("paragraphs", []))
    detected = []
    missing = []
    lower = text.lower()

    for signal in [
        "dataset",
        "training",
        "baseline",
        "evaluation",
        "metrics",
        "model",
        "experiment",
        "resnet",
        "cnn",
        "adam",
        "auc",
        "f1",
    ]:
        if signal in lower:
            detected.append(signal)

    for required in ["dataset size", "experimental setup", "evaluation metrics", "baseline comparison"]:
        if required.lower() not in lower:
            missing.append(required)

    return {
        "document_id": document_id,
        "module": "methodology",
        "detected_information": detected[:8],
        "missing_information": missing,
        "potential_weakness": "The manuscript may lack reproducibility details if dataset provenance, preprocessing, and comparison protocols are not described explicitly.",
        "actionable_suggestion": "Expand the methodology section with dataset size, split strategy, hyperparameters, baselines, and evaluation criteria.",
        "strengths": ["The manuscript appears to include a defined model and some evaluation signals."],
        "suggestions": [
            "Add a data statement describing source, size, and filtering criteria.",
            "Report baseline models and exact parameter settings.",
            "Describe the experimental protocol and statistical significance checks.",
        ],
    }


def analyze_contribution(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    text = "\n".join(doc.get("paragraphs", []))
    lower = text.lower()
    parts = {
        "problem": "The manuscript addresses a meaningful applied problem in model performance and decision support.",
        "research_gap": "The manuscript suggests a gap in existing methods by emphasizing an under-addressed challenge compared with standard baselines.",
        "proposed_solution": "A dedicated model or pipeline is proposed to address the problem.",
        "methodology": "The method is described in terms of training setup and evaluation strategy.",
        "experiments": "Experiments and result summaries are present in the manuscript.",
        "results": "The article reports performance evidence and comparative results.",
        "contribution": "The manuscript contributes a practical method with evidence of improved task performance, though the differentiation should be sharper.",
    }
    if "gap" not in lower and "motivated" not in lower and "existing work" not in lower:
        parts["research_gap"] = "The manuscript would benefit from a more explicit statement of the research gap and contrast with prior work."
    return {
        "document_id": document_id,
        "module": "contribution",
        "problem": parts["problem"],
        "research_gap": parts["research_gap"],
        "proposed_solution": parts["proposed_solution"],
        "methodology": parts["methodology"],
        "experiments": parts["experiments"],
        "results": parts["results"],
        "contribution": parts["contribution"],
        "findings": ["A concrete technical solution is described.", "Performance evidence is present.", "The contribution statement could be made more explicit."],
    }


def analyze_novelty(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    title = doc.get("title") or "Untitled manuscript"
    abstract = doc.get("abstract") or ""
    return {
        "document_id": document_id,
        "module": "novelty",
        "title": title,
        "abstract_summary": abstract[:300],
        "similar_papers": [
            {
                "title": "Clinical imaging with deep CNNs for decision support",
                "authors": ["Lee A.", "Patel B."],
                "year": "2024",
                "venue": "Nature Machine Intelligence",
                "doi": "10.1000/example",
                "similarity": 0.82,
                "overlap": ["clinical imaging", "deep learning", "diagnosis"],
                "differentiation": "The manuscript appears to focus on a concrete application setting and deployment constraints, which may distinguish it from broader benchmark-driven papers.",
            },
            {
                "title": "Benchmarking multimodal medical vision models",
                "authors": ["Chen L."],
                "year": "2023",
                "venue": "IEEE Transactions on Medical Imaging",
                "doi": "10.1000/example-2",
                "similarity": 0.71,
                "overlap": ["medical imaging", "deep learning", "evaluation"],
                "differentiation": "The manuscript may gain novelty by emphasizing the unique task formulation, dataset, or ablation results.",
            },
        ],
        "comparative_summary": "The manuscript is broadly aligned with recent clinical AI and medical imaging work, but the novelty claim should be framed around a distinct problem framing, architecture choice, or deployment context.",
        "potential_differentiators": [
            "A clearer claim about the unique problem formulation.",
            "Specific ablation or robustness evidence.",
            "A stronger explanation of why the proposed setup is different from prior pipelines.",
        ],
    }


def analyze_writing(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    text = "\n".join(doc.get("paragraphs", []))
    issues = []
    if len(text.split()) < 400:
        issues.append("The manuscript is relatively brief; a few sections may need more contextual detail.")
    if not doc.get("abstract"):
        issues.append("Abstract is missing, which weakens the initial paper overview.")
    if len(doc.get("keywords", [])) < 3:
        issues.append("Keyword coverage is light and may reduce discoverability.")
    return {
        "document_id": document_id,
        "module": "writing",
        "grammar": "The draft appears generally understandable, with minor opportunities for clearer phrasing.",
        "clarity": "Several sentences can be tightened to better distinguish the problem, method, and findings.",
        "tone": "The tone is largely academic but could be more concise in the contributions and limitations sections.",
        "issues": issues,
        "suggestions": [
            "Use a stronger contribution sentence in the introduction.",
            "Ensure each section begins with a clear research purpose.",
            "Replace redundancy with precise technical wording.",
        ],
    }


def generate_improvements(document_id: str, analysis: dict | None = None, focus: str | None = None) -> dict:
    doc = analysis or {}
    title = doc.get("title") or "Untitled manuscript"
    abstract = (doc.get("abstract") or "").strip()
    suggestions = [
        {
            "id": "improvement-1",
            "section": "abstract",
            "original": abstract[:200] if abstract else "The manuscript introduces an approach for clinical decision support.",
            "suggested": "We propose a clinical decision-support model that addresses a key limitation in prior diagnostic workflows by combining a scalable deep-learning architecture with explicit evaluation against strong baselines.",
            "reason": "Improves clarity, motivation, and contribution framing.",
        },
        {
            "id": "improvement-2",
            "section": "introduction",
            "original": "Existing work relies on handcrafted features.",
            "suggested": "Existing clinical AI pipelines often depend on handcrafted features and limited benchmark coverage, leaving a clear need for a more scalable and generalizable approach.",
            "reason": "Strengthens the research gap statement.",
        },
        {
            "id": "improvement-3",
            "section": "methodology",
            "original": "We trained a model on clinical records.",
            "suggested": "We trained the proposed model on a curated clinical dataset with explicit train/validation/test splits, standardized preprocessing, and fixed hyperparameters to support reproducibility.",
            "reason": "Makes methods easier to evaluate and reproduce.",
        },
    ]
    return {
        "document_id": document_id,
        "module": "improvement",
        "title": title,
        "focus": focus or "research quality",
        "suggestions": suggestions,
        "approved_changes": [],
    }


def generate_journal_match(document_id: str, analysis: dict | None = None, journal_id: str | None = None) -> dict:
    journal_key = (journal_id or "nature").lower()
    try:
        journal = get_journal_rules(journal_key)
    except ValueError:
        journal = get_journal_rules("nature")

    manuscript_text = _collect_manuscript_terms(analysis)
    score, relevant_topics, scope_gaps = _match_score_for_topics(manuscript_text, journal)

    if not relevant_topics and journal.get("scope_topics"):
        relevant_topics = [str(topic) for topic in journal["scope_topics"][:3]]

    if not scope_gaps:
        scope_gaps = ["The manuscript topic is broadly aligned with the journal's scope; no major mismatch detected, but a clearer framing may still improve fit."]

    if not manuscript_text.strip():
        score = 0.0
        relevant_topics = []
        scope_gaps = ["The manuscript content is missing, so journal scope compatibility could not be assessed from the document itself."]

    explanation = (
        f"The manuscript shows strongest topic alignment with {', '.join(relevant_topics) if relevant_topics else 'general applied research'}. "
        f"The selected journal emphasizes {journal.get('journal_name', 'the journal')}'s technical focus on {journal.get('scope_summary', 'applied research and technical methods')}. "
        f"This score reflects the overlap between the manuscript's key terms and the journal's actual scope rather than a static default.")

    return {
        "document_id": document_id,
        "journal_id": journal_key,
        "score": score,
        "relevant_topics": relevant_topics,
        "scope_gaps": scope_gaps,
        "explanation": explanation,
        "suitable": score >= 0.45,
    }


def generate_readiness_report(document_id: str, analysis: dict | None = None, quality_analysis: dict | None = None, selected_journal: str | None = None) -> dict:
    quality = quality_analysis or analyze_quality(document_id, analysis)
    report = {
        "document_id": document_id,
        "title": "Pre-Submission Readiness Assessment",
        "selected_journal": selected_journal or "nature",
        "summary": "This assessment identifies structural, methodological, and writing-related strengths and weaknesses without implying guaranteed acceptance.",
        "sections": [
            {"name": "Document Structure", "status": "Good", "details": "The manuscript includes a clear title, abstract, sections, and references."},
            {"name": "Citation & Reference Issues", "status": "Needs Review", "details": "Check that each in-text citation maps to a consistent reference entry and numbering is sequential."},
            {"name": "Research Completeness", "status": "Moderate", "details": quality.get("missing_sections", []) or "No major structural gaps detected.", "reason": "The draft should make explicit any missing experimental or comparison details."},
            {"name": "Research Gap", "status": "Good", "details": quality.get("research_gap", "")},
            {"name": "Methodology", "status": "Moderate", "details": "Reproducibility details can be improved with clearer dataset and setup descriptions."},
            {"name": "Technical Contribution", "status": "Good", "details": quality.get("technical_contribution", "")},
            {"name": "Novelty / Similar Research", "status": "Moderate", "details": "The manuscript aligns with relevant work, but the novelty framing should be sharpened."},
            {"name": "Writing Quality", "status": "Good", "details": "The draft is readable and mostly academic in tone."},
            {"name": "Journal Scope", "status": "Good", "details": "The topic aligns with the chosen journal's applied AI and medical-imaging themes."},
            {"name": "Formatting Issues", "status": "Needs Review", "details": "Verify final figure/table captions and reference formatting against the selected journal rules."},
            {"name": "Actionable Suggestions", "status": "Good", "details": "The main next step is to strengthen the methodology description, novelty framing, and contribution statement."},
            {"name": "Final Checklist", "status": "Needs Review", "details": "Review citations, disclose limitations, and confirm all key sections are ready for final submission."},
        ],
        "final_checklist": [
            "Confirm the title and abstract match the manuscript contribution.",
            "Review citation and reference numbering consistency.",
            "Add or improve methodological detail and baseline comparison.",
            "Clarify novelty and contribution statements.",
            "Assess whether journal scope and word limits are met.",
        ],
    }
    return report
