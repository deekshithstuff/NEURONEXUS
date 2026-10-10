from __future__ import annotations

import json
import re
from typing import Any

from backend.citation.validator import validate_citations
from backend.journal.rules import get_available_journals, get_journal_rules


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _normalize_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.findall(r"[a-z0-9]+", (value or "").lower()) if token}


def _section_text(analysis: dict | None, section_type: str) -> str:
    if not isinstance(analysis, dict):
        return ""
    aliases = {
        "methodology": {"methodology", "methods", "materials and methods"},
        "results": {"results", "findings"},
    }
    accepted = aliases.get(section_type, {section_type})
    return " ".join(
        str(section.get("content") or "")
        for section in analysis.get("sections", [])
        if isinstance(section, dict)
        and (section.get("type", "").lower() in accepted or section.get("heading", "").lower() in accepted)
    )


def _evidence_score(signals: list[bool], base: int = 0) -> int:
    if not signals:
        return 0
    return min(100, round(base + (sum(signals) / len(signals)) * (100 - base)))


def _detected_section_types(analysis: dict | None) -> set[str]:
    if not isinstance(analysis, dict):
        return set()
    types = set()
    for section in analysis.get("sections", []):
        if not isinstance(section, dict):
            continue
        types.add(str(section.get("type") or "").lower().replace(" ", "_"))
        types.add(str(section.get("heading") or "").lower().replace(" ", "_"))
    return types


def _novelty_evidence(analysis: dict | None) -> dict:
    document = analysis or {}
    text = _collect_manuscript_terms(document).lower()
    gap_phrases = ("research gap", "little is known", "few studies", "limited work", "has not been", "remains unexplored")
    contribution_phrases = ("we propose", "our contribution", "this study contributes", "we present", "we introduce")
    comparison_phrases = ("prior work", "existing work", "compared with", "baseline", "state-of-the-art")
    gap_clear = any(phrase in text for phrase in gap_phrases)
    contribution_clear = any(phrase in text for phrase in contribution_phrases)
    comparison_present = any(phrase in text for phrase in comparison_phrases)
    method_present = bool(_section_text(document, "methodology") or re.search(r"\b(method|model|algorithm|approach)\b", text))
    results_present = bool(_section_text(document, "results") or re.search(r"\b(results?|accuracy|\d+(?:\.\d+)?%)\b", text))
    keywords_present = len(document.get("keywords") or []) >= 3
    score = _evidence_score([gap_clear, contribution_clear, comparison_present, method_present, results_present, keywords_present])
    return {
        "novelty_score": score,
        "research_gap_clarity": _evidence_score([gap_clear, comparison_present]),
        "contribution_strength": _evidence_score([contribution_clear, method_present, results_present]),
        "evidence": {
            "explicit_research_gap": gap_clear,
            "explicit_contribution_claim": contribution_clear,
            "prior_work_or_baseline_comparison": comparison_present,
            "method_or_approach_described": method_present,
            "results_evidence_present": results_present,
            "keywords_present": keywords_present,
        },
    }


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


_SCOPE_STOP_WORDS = {
    "a", "an", "and", "article", "applied", "empirical", "evaluation", "general",
    "computer", "interdisciplinary", "journal", "method", "methods", "of", "paper", "research",
    "science", "study", "studies", "system", "systems", "the", "with",
}


def _match_score_for_topics(analysis: dict, journal: dict | None) -> tuple[float | None, list[str], list[str], str]:
    fields = {
        "title": (str(analysis.get("title") or ""), 1.5),
        "abstract": (str(analysis.get("abstract") or ""), 1.2),
        "keywords": (" ".join(str(item) for item in analysis.get("keywords") or []), 1.5),
        "sections": (_section_text_for_match(analysis), 1.0),
        "subject_area": (str(analysis.get("subject_area") or analysis.get("metadata", {}).get("subject_area") or ""), 1.5),
    }
    manuscript_tokens = set().union(*(_normalize_tokens(value) for value, _ in fields.values()))
    if len(manuscript_tokens - _SCOPE_STOP_WORDS) < 6:
        return None, [], ["Insufficient manuscript content for a reliable journal-scope comparison."], "insufficient_content"

    if not isinstance(journal, dict):
        return None, [], ["The selected journal profile is unavailable; scope compatibility cannot be assessed."], "scope_unavailable"

    raw_topics = [str(item) for item in journal.get("scope_topics") or []]
    aliases = journal.get("scope_aliases") or {}
    for label, values in aliases.items():
        raw_topics.append(str(label))
        if isinstance(values, (list, tuple, set)):
            raw_topics.extend(str(value) for value in values)
    topics = list(dict.fromkeys(_normalize_text(topic).lower() for topic in raw_topics if _normalize_text(topic)))
    topics = [topic for topic in topics if _normalize_tokens(topic) - _SCOPE_STOP_WORDS]
    if not topics:
        return None, [], ["This profile does not contain configured scope topics; suitability is unknown."], "scope_unavailable"

    supported: list[tuple[str, float]] = []
    for topic in topics:
        topic_tokens = _normalize_tokens(topic) - _SCOPE_STOP_WORDS
        strength = 0.0
        for value, field_weight in fields.values():
            normalized_value = _normalize_text(value).lower()
            value_tokens = _normalize_tokens(value)
            if re.search(rf"\b{re.escape(topic)}\b", normalized_value):
                strength = max(strength, field_weight)
                continue
            overlap = topic_tokens & value_tokens
            if len(topic_tokens) == 1 and overlap:
                strength = max(strength, field_weight * 0.8)
            elif len(overlap) >= 2 and len(overlap) / len(topic_tokens) >= 0.67:
                strength = max(strength, field_weight * 0.65)
        if strength:
            supported.append((topic, min(1.0, strength / 1.5)))

    score = round(sum(strength for _, strength in supported) / len(topics), 4)
    matched_topics = [topic for topic, _ in sorted(supported, key=lambda item: (-item[1], item[0]))]
    gaps = []
    if not matched_topics:
        gaps.append("No configured journal-scope topics were found in the manuscript fields that were analyzed.")
    elif score < 0.2:
        gaps.append("Only limited scope evidence was found; review the journal's current aims and instructions.")
    elif score < 0.4:
        gaps.append("The manuscript has partial scope overlap; review the journal's current aims and instructions.")
    return score, matched_topics, gaps, "evaluated"


def _section_text_for_match(analysis: dict) -> str:
    return " ".join(
        f"{section.get('heading') or ''} {section.get('content') or ''}"
        for section in analysis.get("sections") or []
        if isinstance(section, dict)
    )


def analyze_quality(document_id: str, analysis: dict | None = None, journal_id: str | None = None) -> dict:
    document = analysis or {}
    content_word_count = len(_collect_manuscript_terms(document).split())
    insufficient_content = content_word_count < 40
    paragraphs = document.get("paragraphs") or [""]
    body = _normalize_text(document.get("abstract") or paragraphs[0])
    journal = get_journal_rules((journal_id or "nature").lower())
    sections = _detected_section_types(document)
    required_sections = journal.get("required_sections") or ["abstract", "introduction", "methodology", "results", "conclusion", "references"]
    missing = [required for required in required_sections if required not in sections]
    writing_issues = analyze_writing(document_id, document)["issues"]
    if not document.get("keywords"):
        writing_issues.append("Keywords are missing or too sparse for discovery.")
    if len(body) < 120:
        writing_issues.append("Abstract is short and may not explain the problem, method, and result clearly.")
    introduction = _section_text(document, "introduction").lower()
    gap_present = any(term in introduction for term in ("research gap", "little is known", "few studies", "limited work", "has not been", "remains unexplored"))
    method_analysis = analyze_methodology(document_id, document)
    contribution_analysis = analyze_contribution(document_id, document)
    recommendations = [f"Add or clearly label the {item.replace('_', ' ')} section if required by the selected profile." for item in missing]
    recommendations.extend(method_analysis["suggestions"][:3])
    if not gap_present:
        recommendations.append("State the research gap explicitly in the introduction and distinguish it from prior work.")

    return {
        "document_id": document_id,
        "module": "quality",
        "analysis_status": "insufficient_content" if insufficient_content else "assessed",
        "quality_score": None if insufficient_content else _evidence_score([
            not missing,
            gap_present,
            method_analysis["score"] >= 60,
            contribution_analysis["technical_contribution_score"] >= 60,
            not writing_issues,
        ]),
        "research_gap": "An explicit research-gap signal was detected in the introduction." if gap_present else "No explicit research-gap statement was detected in the parsed introduction.",
        "technical_contribution": f"Evidence checks detected {len(contribution_analysis['strengths'])} of 10 technical contribution signals.",
        "methodology_issues": method_analysis["missing_information"],
        "missing_sections": missing,
        "writing_issues": writing_issues,
        "suggestions": list(dict.fromkeys(recommendations)),
        "analysis_scope": (
            "Insufficient manuscript text for a meaningful quality score; add manuscript content and rerun analysis. "
            if insufficient_content else ""
        ) + f"Rule-based evidence checks against the {journal.get('template_name', journal_id or 'selected')} profile; not a peer review.",
    }


def analyze_methodology(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    text = _section_text(doc, "methodology") or "\n".join(doc.get("paragraphs") or [])
    lower = text.lower()
    checks = [
        ("research methodology", bool(re.search(r"\b(method|methodology|approach|protocol)\b", lower))),
        ("dataset", bool(re.search(r"\b(dataset|data set|corpus|cohort)\b", lower))),
        ("dataset size", bool(re.search(r"\b\d[\d,]*(?:\.\d+)?\s*(?:samples|records|participants|patients|images|documents|observations)\b", lower))),
        ("data source", bool(re.search(r"\b(data source|collected from|obtained from|public dataset|repository)\b", lower))),
        ("preprocessing", bool(re.search(r"\b(preprocess|normaliz|filter|cleaned|augmentation)\w*\b", lower))),
        ("experimental setup", bool(re.search(r"\b(experimental setup|experiment protocol|train.?test split|validation set|study design)\b", lower))),
        ("algorithms or models", bool(re.search(r"\b(model|algorithm|architecture|classifier|regression|network)\b", lower))),
        ("parameters", bool(re.search(r"\b(parameter|hyperparameter|learning rate|epochs|batch size|threshold)\b", lower))),
        ("training procedure", bool(re.search(r"\b(train|training|fine.?tun|optimizer)\w*\b", lower))),
        ("evaluation metrics", bool(re.search(r"\b(metric|accuracy|precision|recall|f1|auc|rmse|mae|bleu)\b", lower))),
        ("baseline methods", bool(re.search(r"\b(baseline|benchmark|compared with|comparison)\b", lower))),
        ("statistical validation", bool(re.search(r"\b(p.?value|confidence interval|statistical|significance test|standard deviation)\b", lower))),
        ("reproducibility information", bool(re.search(r"\b(reproducib|random seed|code available|data availability|software version)\w*\b", lower))),
        ("limitations", bool(re.search(r"\blimitations?\b", lower))),
    ]
    detected = [name for name, present in checks if present]
    missing = [name for name, present in checks if not present]
    strengths = [f"The methodology mentions {name}." for name in detected]
    suggestions = [f"Report {name.lower()} in the methodology where applicable." for name in missing]
    return {
        "document_id": document_id,
        "module": "methodology",
        "score": _evidence_score([present for _, present in checks]),
        "detected_information": detected[:8],
        "missing_information": missing,
        "potential_weakness": "The parsed methodology does not explicitly identify: " + ", ".join(missing) + "." if missing else "The configured methodology evidence checks found no listed gaps; this does not establish methodological validity.",
        "actionable_suggestion": suggestions[0] if suggestions else "No missing evidence was detected by these rule-based checks.",
        "strengths": strengths,
        "suggestions": suggestions,
        "analysis_scope": "Rule-based text checks; scientific validity and unmentioned details require human review.",
    }


def analyze_contribution(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    text = _collect_manuscript_terms(doc)
    lower = text.lower()
    method = _section_text(doc, "methodology").lower()
    results = _section_text(doc, "results").lower()
    checks = [
        ("problem significance", bool(doc.get("title") and (doc.get("abstract") or _section_text(doc, "introduction")))),
        ("technical novelty framing", any(term in lower for term in ("research gap", "novel", "little is known", "limited work"))),
        ("proposed method", bool(re.search(r"\b(we propose|we present|we introduce|our method|our approach)\b", lower))),
        ("algorithm or model contribution", bool(re.search(r"\b(algorithm|model|architecture|framework|method)\b", lower))),
        ("implementation contribution", bool(re.search(r"\b(implementation|prototype|system|software|code)\b", lower))),
        ("experimental contribution", bool(results)),
        ("baseline comparison", bool(re.search(r"\b(baseline|compared with|comparison|state-of-the-art)\b", lower))),
        ("measurable results", bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|ms|seconds?|accuracy|f1|auc|rmse)\b", results))),
        ("reproducibility", bool(re.search(r"\b(reproducib|random seed|code available|data availability)\w*\b", method))),
        ("limitations", bool(re.search(r"\blimitations?\b", lower))),
    ]
    strengths = [name for name, present in checks if present]
    missing = [name for name, present in checks if not present]
    suggestions = [f"Add manuscript evidence for {name.lower()} or explain why it is not applicable." for name in missing]
    return {
        "document_id": document_id,
        "module": "contribution",
        "technical_contribution_score": _evidence_score([present for _, present in checks]),
        "strengths": strengths,
        "weaknesses": missing,
        "missing_evidence": missing,
        "recommendations": suggestions,
        "analysis_scope": "Evidence-presence assessment only; it does not determine scientific importance or validate claims.",
    }


def analyze_novelty(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    evidence = _novelty_evidence(doc)
    missing = [label for key, label in [
        ("explicit_research_gap", "State the research gap and contrast it with prior work."),
        ("explicit_contribution_claim", "Add a specific contribution claim."),
        ("prior_work_or_baseline_comparison", "Compare the approach with relevant prior work or baselines."),
        ("results_evidence_present", "Connect novelty claims to measurable results."),
    ] if not evidence["evidence"][key]]
    return {
        "document_id": document_id,
        "module": "novelty",
        **evidence,
        "originality_score": None,
        "originality_status": "not_configured",
        "analysis_scope": "Internal manuscript analysis only; no external scholarly search or global similarity check is configured.",
        "potential_overlap_indicators": [],
        "explanation": "The novelty score measures clarity of novelty-related evidence in this manuscript. It does not verify global originality.",
        "improvement_suggestions": missing,
    }


def analyze_completeness(document_id: str, analysis: dict | None = None, journal_id: str | None = None) -> dict:
    document = analysis or {}
    journal = get_journal_rules((journal_id or "nature").lower())
    detected = _detected_section_types(document)
    if document.get("title"):
        detected.add("title")
    if document.get("abstract"):
        detected.add("abstract")
    if document.get("keywords"):
        detected.add("keywords")
    if document.get("references"):
        detected.add("references")
    intro = _section_text(document, "introduction").lower()
    if any(term in intro for term in ("research gap", "little is known", "few studies", "limited work", "has not been", "remains unexplored")):
        detected.add("research_gap")
    canonical = [
        "title", "abstract", "keywords", "introduction", "related_work", "research_gap",
        "methodology", "results", "discussion", "conclusion", "limitations", "future_work", "references",
    ]
    required = list(journal.get("required_sections") or [])
    optional = list(journal.get("optional_sections") or [])
    missing_required = [item for item in required if item not in detected]
    present_optional = [item for item in optional if item in detected]
    missing_optional = [item for item in optional if item not in detected]
    figure_warnings = [figure.get("id") for figure in document.get("figures") or [] if isinstance(figure, dict) and not figure.get("caption")]
    table_warnings = [table.get("id") for table in document.get("tables") or [] if isinstance(table, dict) and not table.get("caption")]
    unnumbered_equations = [equation.get("id") for equation in document.get("equations") or [] if isinstance(equation, dict) and not equation.get("number")]
    word_count = len(_collect_manuscript_terms(document).split())
    word_limit = journal.get("word_limit")
    abstract_limit = (journal.get("abstract_formatting") or {}).get("max_words")
    abstract_word_count = len(str(document.get("abstract") or "").split())
    word_limit_exceeded = bool(word_limit and word_count > word_limit)
    abstract_limit_exceeded = bool(abstract_limit and abstract_word_count > abstract_limit)
    score = round(100 * (len(required) - len(missing_required)) / len(required)) if required else 100
    return {
        "document_id": document_id,
        "module": "completeness",
        "score": score,
        "journal_id": journal.get("journal_id"),
        "journal_name": journal.get("journal_name"),
        "canonical_sections": canonical,
        "required_sections": required,
        "optional_sections": optional,
        "detected_sections": sorted(item for item in detected if item in set(canonical + required + optional)),
        "missing_required": missing_required,
        "present_optional": present_optional,
        "missing_optional": missing_optional,
        "missing_figure_captions": figure_warnings,
        "missing_table_captions": table_warnings,
        "unnumbered_equations": unnumbered_equations,
        "word_count": word_count,
        "word_limit": word_limit,
        "word_limit_exceeded": word_limit_exceeded,
        "abstract_word_count": abstract_word_count,
        "abstract_word_limit": abstract_limit,
        "abstract_limit_exceeded": abstract_limit_exceeded,
        "page_limit": journal.get("page_limit"),
        "page_limit_status": "not_assessed" if journal.get("page_limit") else "not_applicable",
        "analysis_scope": f"Section coverage is judged against the selected {journal.get('template_name')} required/optional lists; not every manuscript type needs every canonical section.",
    }


def analyze_writing(document_id: str, analysis: dict | None = None) -> dict:
    doc = analysis or {}
    units = [str(paragraph) for paragraph in doc.get("paragraphs") or []]
    if not units:
        units = [
            str(section.get("content") or "")
            for section in doc.get("sections", [])
            if isinstance(section, dict)
        ]
    issues = []
    findings = []
    informal_terms = ("obviously", "awesome", "huge", "a lot of", "kind of")
    vague_terms = ("various", "several", "some studies", "many researchers", "significant")
    seen_sentences: list[str] = []
    for unit in units:
        for sentence in re.split(r"(?<=[.!?])\s+", unit.strip()):
            words = sentence.split()
            if not sentence:
                continue
            lower = sentence.lower()
            if len(words) > 35:
                problem = f"Long sentence ({len(words)} words) may be difficult to follow."
                issues.append(problem)
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "Consider splitting at a clause boundary while preserving the same claims and relationships.", "reason": "Shorter sentences can make technical arguments easier to evaluate."})
            if any(term in lower for term in informal_terms):
                problem = "Potentially informal or vague wording was detected."
                issues.append(problem)
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "Replace the flagged wording with the precise technical term intended by the authors.", "reason": "Specific terminology is easier to interpret and verify."})
            if any(term in lower for term in vague_terms) and not re.search(r"\d", sentence):
                problem = "Vague quantitative language without a number or cited source."
                issues.append(problem)
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "Replace vague quantity words with the measured value, sample size, or cited evidence.", "reason": "Reviewers need inspectable quantities rather than unspecified magnitude."})
            if re.search(r"\b(outperforms|significantly better|clearly superior)\b", lower) and not re.search(r"\d", sentence):
                problem = "Unsupported comparative claim without a reported quantity."
                issues.append(problem)
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "Attach the comparison to a metric, baseline, and measured difference.", "reason": "Comparative claims should be tied to reported evidence."})
            if re.search(r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b", lower) and len(words) > 18:
                problem = "Long passive construction may hide the actor or method."
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "If the actor matters, recast in active voice without changing the claim.", "reason": "Active voice can make methods and responsibility clearer."})
            normalized = re.sub(r"\s+", " ", lower)
            if normalized in seen_sentences:
                problem = "Repeated sentence or near-duplicate wording."
                issues.append(problem)
                findings.append({"original": sentence, "problem": problem, "suggested_improvement": "Keep one instance and delete the repeated sentence.", "reason": "Redundant sentences add length without new evidence."})
            seen_sentences.append(normalized)
            if len(findings) >= 20:
                break
        if len(findings) >= 20:
            break
    if not doc.get("abstract") and "abstract" not in _detected_section_types(doc):
        issues.append("No abstract text or abstract section was detected.")
    if len(doc.get("keywords") or []) < 3:
        issues.append("Fewer than three keywords were parsed; check the selected journal's keyword requirements.")
    score = max(0, 100 - len(issues) * 8)
    return {
        "document_id": document_id,
        "module": "writing",
        "score": score,
        "grammar": "Not configured; deterministic writing checks do not verify grammar or spelling.",
        "spelling": "Not configured; deterministic writing checks do not verify spelling.",
        "clarity": "Rule-based sentence-length and wording checks only.",
        "tone": "Potentially informal wording is flagged when matched; academic tone is not fully classified.",
        "issues": issues,
        "sentence_findings": findings,
        "suggestions": [item["suggested_improvement"] for item in findings],
        "analysis_scope": "Limited rule-based analysis; no full grammar, spelling, coherence, or terminology model is configured.",
    }


def generate_improvements(document_id: str, analysis: dict | None = None, focus: str | None = None, journal_id: str | None = None) -> dict:
    doc = analysis or {}
    title = doc.get("title") or "Untitled manuscript"
    completeness = analyze_completeness(document_id, doc, journal_id)
    writing = analyze_writing(document_id, doc)
    method_review = analyze_methodology(document_id, doc)
    citation_style = get_journal_rules((journal_id or "nature").lower()).get("citation_style")
    citation_issues = validate_citations(
        doc.get("citations") or [],
        doc.get("references") or [],
        citation_style,
    )
    ranked: list[dict] = []
    for issue in citation_issues["missing_references"]:
        ranked.append(_recommendation("CRITICAL", "References", issue["message"], "Add or correct the matching bibliography entry.", issue["message"]))
    for issue_group, issues in citation_issues.items():
        if issue_group == "missing_references":
            continue
        for issue in issues:
            severity = str(issue.get("severity") or "medium").upper()
            category = severity if severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "MEDIUM"
            ranked.append(_recommendation(
                category,
                "References",
                issue["message"],
                issue.get("suggestion") or "Review the bibliography against the selected journal's reference requirements.",
                issue["message"],
                issue.get("citation"),
            ))
    for missing in completeness["missing_required"]:
        ranked.append(_recommendation("HIGH", missing, f"Required section not detected: {missing}.", f"Add or clearly label the {missing.replace('_', ' ')} section if it is required by the selected profile.", "The selected journal profile lists this among required sections."))
    if completeness["missing_figure_captions"]:
        ranked.append(_recommendation("HIGH", "Figures", f"Missing figure captions: {', '.join(completeness['missing_figure_captions'])}.", "Add a caption below each figure.", "Parsed figures have no caption text."))
    if completeness["missing_table_captions"]:
        ranked.append(_recommendation("HIGH", "Tables", f"Missing table captions: {', '.join(completeness['missing_table_captions'])}.", "Add a caption above each table.", "Parsed tables have no caption text."))
    for missing in method_review["missing_information"][:6]:
        ranked.append(_recommendation("HIGH", "methodology", f"Methodology does not clearly identify {missing.lower()}.", f"Report {missing.lower()} where applicable.", f"The methodology text does not clearly identify {missing.lower()}."))
    intro = _section_text(doc, "introduction").lower()
    if intro and not any(term in intro for term in ("research gap", "little is known", "few studies", "limited work", "has not been")):
        ranked.append(_recommendation("MEDIUM", "introduction", "No explicit research-gap signal was detected in the introduction.", "State the research gap and distinguish it from cited prior work.", "Novelty framing is weaker without an explicit gap statement."))
    if completeness["unnumbered_equations"]:
        ranked.append(_recommendation("MEDIUM", "Equations", f"Unnumbered equations: {', '.join(completeness['unnumbered_equations'])}.", "Number displayed equations according to the selected journal profile.", "Parsed equations do not include a visible number."))
    if completeness["word_limit_exceeded"]:
        ranked.append(_recommendation("HIGH", "Manuscript", f"Manuscript exceeds the configured word limit ({completeness['word_count']} / {completeness['word_limit']}).", "Shorten the manuscript to the selected profile's word limit and recheck the count.", "The selected journal profile has a configured word limit."))
    if completeness["abstract_limit_exceeded"]:
        ranked.append(_recommendation("MEDIUM", "Abstract", f"Abstract exceeds the configured word limit ({completeness['abstract_word_count']} / {completeness['abstract_word_limit']}).", "Edit the abstract to meet the selected profile's word limit.", "The selected journal profile has a configured abstract limit."))
    for finding in writing["sentence_findings"][:5]:
        ranked.append(_recommendation("LOW", "writing", finding["problem"], finding["suggested_improvement"], finding["reason"], finding["original"]))

    suggestions = []
    for index, item in enumerate(ranked, start=1):
        suggestions.append({
            "id": f"improvement-{index}",
            "category": item["category"],
            "severity": item["severity"],
            "priority": item["priority"],
            "section": item["affected_section"],
            "issue": item["issue"],
            "original": item["original"],
            "suggested": item["suggested_action"],
            "reason": item["explanation"],
            "action_type": "recommendation",
            "replacement": None,
            "can_apply": False,
        })
    return {
        "document_id": document_id,
        "module": "improvement",
        "title": title,
        "focus": focus or "research quality",
        "suggestions": suggestions,
        "approved_changes": [],
        "source_modified": False,
    }


def _flexible_search(raw: str, needle: str):
    """Return a compiled, whitespace-flexible and case-insensitive regex for needle."""
    parts = [re.escape(part) for part in needle.split() if part]
    if not parts:
        return None
    return re.compile(r"\s+".join(parts), flags=re.IGNORECASE)


def _locate_all_text_targets(document: dict, original: str) -> list[dict]:
    """Find every place in the analysis where original appears.

    Each result is dict with location + mutation metadata. Locations are
    section content, individual paragraphs, or the abstract.
    """
    targets: list[dict] = []
    sections = document.get("sections") or []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        raw = str(section.get("content") or "")
        pattern = _flexible_search(raw, original)
        if pattern and pattern.search(raw):
            targets.append({"kind": "section", "index": index, "key": "content", "raw": raw, "expression": pattern})
    paragraphs = document.get("paragraphs") or []
    for index, paragraph in enumerate(paragraphs):
        raw = str(paragraph)
        pattern = _flexible_search(raw, original)
        if pattern and pattern.search(raw):
            targets.append({"kind": "paragraph", "index": index, "key": "content", "raw": raw, "expression": pattern})
    raw = str(document.get("abstract") or "")
    pattern = _flexible_search(raw, original)
    if pattern and pattern.search(raw):
        targets.append({"kind": "abstract", "index": None, "key": "abstract", "raw": raw, "expression": pattern})
    return targets


def apply_approved_changes(analysis: dict | None, approved_changes: list[dict]) -> tuple[dict, list[dict], list[dict]]:
    """Apply user-accepted improvement suggestions to a copy of the analysis.

    Returns (modified_analysis, applied_changes, skipped_changes).
    """
    document = json.loads(json.dumps(analysis or {}, default=str))
    applied: list[dict] = []
    skipped: list[dict] = []
    for change in approved_changes or []:
        if not change.get("accepted") and not change.get("accept"):
            skipped.append({**change, "applied": False, "reason": "Change was not accepted by the user."})
            continue
        original = _normalize_text(change.get("original") or "")
        if not original or original.startswith("No source sentence found"):
            skipped.append({**change, "applied": False, "reason": "No editable source sentence found for this suggestion."})
            continue
        replacement = _normalize_text(change.get("replacement") or "")
        if change.get("action_type") != "replace_text" or not replacement:
            skipped.append({**change, "applied": False, "reason": "Advisory suggestions do not contain a validated replacement."})
            continue
        suggested = replacement
        if not suggested or original == suggested:
            skipped.append({**change, "applied": False, "reason": "No editable source sentence found for this suggestion."})
            continue
        targets = _locate_all_text_targets(document, original)
        if not targets:
            skipped.append({**change, "applied": False, "reason": "Original text could not be matched in the manuscript content."})
            continue
        matched_any = False
        locations: list[str] = []
        for target in targets:
            match = target["expression"].search(target["raw"])
            if not match:
                continue
            start, end = match.span()
            replaced = target["raw"][:start] + suggested + target["raw"][end:]
            if target["kind"] == "section":
                sections = document.setdefault("sections", [])
                sections[target["index"]][target["key"]] = replaced
            elif target["kind"] == "paragraph":
                document["paragraphs"][target["index"]] = replaced
            else:
                document["abstract"] = replaced
            matched_any = True
            if target["kind"] not in locations:
                locations.append(target["kind"])
        if not matched_any:
            skipped.append({**change, "applied": False, "reason": "Original text could not be matched in the manuscript content."})
            continue
        applied.append({
            "id": change.get("id"),
            "section": change.get("section"),
            "issue": change.get("issue"),
            "original": original,
            "suggested": suggested,
            "applied": True,
            "location": ", ".join(locations),
        })
    return document, applied, skipped


def generate_journal_match(document_id: str, analysis: dict | None = None, journal_id: str | None = None) -> dict:
    journal_key = (journal_id or "nature").lower()
    journal = get_journal_rules(journal_key)
    document = analysis or {}
    manuscript_text = _collect_manuscript_terms(document)
    article_type = str(
        document.get("article_type")
        or document.get("metadata", {}).get("article_type")
        or ""
    ).strip()
    section_types = _detected_section_types(document)
    word_count = len(manuscript_text.split())
    abstract_words = len(str(document.get("abstract") or "").split())

    def profile_metrics(candidate: dict) -> dict:
        scope_score, topics, gaps, scope_status = _match_score_for_topics(document, candidate)
        required = set(candidate.get("required_sections") or [])
        missing_sections = sorted(required - section_types)
        word_limit = candidate.get("word_limit")
        abstract_limit = (candidate.get("abstract_formatting") or {}).get("max_words")
        keyword_rules = candidate.get("keyword_rules") or {}
        formatting_checks = []
        if required:
            formatting_checks.append(not missing_sections)
        if word_limit:
            formatting_checks.append(bool(word_count) and word_count <= word_limit)
        if abstract_limit:
            formatting_checks.append(bool(abstract_words) and abstract_words <= abstract_limit)
        if keyword_rules.get("required"):
            formatting_checks.append(bool(document.get("keywords")))
        formatting_score = round(100 * sum(formatting_checks) / len(formatting_checks)) if formatting_checks else None
        expected_article = str(candidate.get("article_type") or "").strip().lower()
        article_match = None
        if article_type and expected_article:
            article_match = (
                article_type.lower() == expected_article
                or article_type.lower() in expected_article
                or expected_article in article_type.lower()
            )
        components = []
        if scope_score is not None:
            components.append((scope_score, 0.65))
        if formatting_score is not None:
            components.append((formatting_score / 100, 0.25))
        if article_match is not None:
            components.append((1.0 if article_match else 0.0, 0.10))
        suitability = (
            round(sum(value * weight for value, weight in components) / sum(weight for _, weight in components), 4)
            if components and scope_status == "evaluated" else None
        )
        requirements = [f"Required section not detected: {name}." for name in missing_sections]
        if word_limit and word_count > word_limit:
            requirements.append(f"Word limit exceeded: {word_count} words versus {word_limit} configured.")
        if abstract_limit and abstract_words > abstract_limit:
            requirements.append(f"Abstract exceeds configured limit: {abstract_words} words versus {abstract_limit}.")
        if keyword_rules.get("required") and not document.get("keywords"):
            requirements.append("The selected profile requires keywords, but none were detected.")
        if article_match is False:
            requirements.append(f"Article type '{article_type}' does not match the configured '{expected_article}' profile.")
        if scope_status != "evaluated":
            requirements.append("Scope suitability is unknown because manuscript content or configured journal scope is insufficient.")
        if gaps:
            scope_gaps = gaps
        elif not manuscript_text.strip():
            scope_gaps = ["The manuscript content is missing, so journal scope compatibility could not be assessed from the document itself."]
        else:
            scope_gaps = ["The manuscript topic is broadly aligned with the journal's scope; a clearer framing may still improve fit."]
        return {
            "scope_score": scope_score,
            "topics": topics,
            "scope_gaps": scope_gaps,
            "missing_sections": missing_sections,
            "requirements": requirements,
            "article_type_match": article_match,
            "formatting_score": formatting_score,
            "suitability_score": suitability,
            "scope_status": scope_status,
        }

    selected = profile_metrics(journal)
    score = selected["scope_score"]
    relevant_topics = selected["topics"]
    scope_gaps = selected["scope_gaps"]
    if selected["scope_status"] == "evaluated":
        evidence = ", ".join(relevant_topics[:5]) or "no matching configured scope phrases"
        explanation = (
            f"Scope evidence score is {round(score * 100)}%, based on matched configured topics: {evidence}. "
            "Suitability uses only configured scope, requirements, and supplied article-type evidence; it is not an acceptance probability. "
            f"{journal.get('profile_basis', 'Profile basis not specified')}"
        )
    else:
        explanation = f"{scope_gaps[0]} Profile basis: {journal.get('profile_basis', 'Not specified')}"
    ranked_by_id = {}
    for candidate in get_available_journals():
        candidate_id = candidate.get("journal_id")
        if not candidate_id or candidate_id in ranked_by_id:
            continue
        metrics = profile_metrics(candidate)
        ranked_by_id[candidate_id] = {
            "journal_id": candidate_id,
            "journal_name": candidate["journal_name"],
            "score": metrics["suitability_score"],
            "suitability_score": metrics["suitability_score"],
            "scope_match": metrics["scope_score"],
            "formatting_compatibility": metrics["formatting_score"],
            "article_type_match": metrics["article_type_match"],
            "match_status": metrics["scope_status"],
            "missing_requirements": metrics["requirements"],
            "relevant_topics": metrics["topics"],
        }
    ranked_journals = list(ranked_by_id.values())
    ranked_journals.sort(
        key=lambda item: (
            item["score"] if item["score"] is not None else -1,
            item["scope_match"] if item["scope_match"] is not None else -1,
        ),
        reverse=True,
    )
    return {
        "document_id": document_id,
        "journal_id": journal_key,
        "score": score,
        "scope_match": score,
        "topic_match": score,
        "match_status": selected["scope_status"],
        "article_type": article_type or "not provided",
        "article_type_match": selected["article_type_match"],
        "formatting_compatibility": selected["formatting_score"],
        "suitability_score": selected["suitability_score"],
        "missing_requirements": selected["requirements"],
        "ranked_journals": ranked_journals,
        "relevant_topics": relevant_topics,
        "scope_gaps": scope_gaps,
        "explanation": explanation,
        "suitable": selected["suitability_score"] is not None and selected["suitability_score"] >= 0.45,
        "acceptance_guarantee": False,
    }


def generate_readiness_report(document_id: str, analysis: dict | None = None, quality_analysis: dict | None = None, selected_journal: str | None = None) -> dict:
    document = analysis or {}
    journal_id = (selected_journal or "nature").lower()
    journal = get_journal_rules(journal_id)
    quality = quality_analysis or analyze_quality(document_id, document, journal_id)
    section_types = _detected_section_types(document)
    required_sections = set(journal.get("required_sections") or ["abstract", "introduction", "methodology", "results", "conclusion", "references"])
    section_score = round(100 * len(required_sections & section_types) / len(required_sections)) if required_sections else 100
    citations = document.get("citations") or []
    references = document.get("references") or []
    citation_issues = validate_citations(citations, references, journal.get("citation_style"))
    issue_count = sum(len(items) for items in citation_issues.values())
    severity_penalty = sum(
        {"high": 20, "medium": 8, "low": 3}.get(str(issue.get("severity", "")).lower(), 0)
        for items in citation_issues.values()
        for issue in items
    )
    citation_score = 0 if not citations and not references else max(0, 100 - severity_penalty)
    methodology = analyze_methodology(document_id, document)
    method_score = methodology["score"]
    novelty = _novelty_evidence(document)
    contribution = analyze_contribution(document_id, document)
    contribution_score = contribution["technical_contribution_score"]
    text = _collect_manuscript_terms(document)
    writing = analyze_writing(document_id, document)
    writing_score = writing["score"]
    completeness = analyze_completeness(document_id, document, journal_id)
    journal_match = generate_journal_match(document_id, document, journal_id)
    word_count = len(text.split())
    abstract_limit = (journal.get("abstract_formatting") or {}).get("max_words")
    formatting_checks = [
        not journal.get("word_limit") or word_count <= journal["word_limit"],
        not abstract_limit or len(str(document.get("abstract") or "").split()) <= abstract_limit,
        not (journal.get("keyword_rules") or {}).get("required") or bool(document.get("keywords")),
        not completeness["missing_figure_captions"],
        not completeness["missing_table_captions"],
        not completeness["unnumbered_equations"],
    ]
    formatting_score = round(100 * sum(formatting_checks) / len(formatting_checks))
    completeness_score = completeness["score"]
    scores = {
        "structure": section_score,
        "citation_consistency": citation_score,
        "research_completeness": completeness_score,
        "methodology": method_score,
        "technical_contribution": contribution_score,
        "novelty_framing": novelty["novelty_score"],
        "writing_quality": writing_score,
        "journal_suitability": round(journal_match["suitability_score"] * 100) if journal_match["suitability_score"] is not None else 0,
        "formatting_compliance": formatting_score,
    }
    overall = round(sum(scores.values()) / len(scores))
    sections = [
        {"name": label, "score": score, "status": "Good" if score >= 80 else "Moderate" if score >= 60 else "Needs Review", "details": detail}
        for label, score, detail in [
            ("Document Structure", scores["structure"], f"Detected {len(required_sections & section_types)} of {len(required_sections)} core sections."),
            ("Citation & Reference Consistency", citation_score, f"Found {issue_count} citation/reference issue(s)."),
            ("Research Completeness", scores["research_completeness"], "Core section coverage based on parsed headings."),
            ("Methodology", method_score, f"Detected {len(methodology['detected_information'])} evidence groups; {len(methodology['missing_information'])} are not explicit."),
            ("Technical Contribution", contribution_score, f"Detected {len(contribution['strengths'])} of 10 contribution evidence signals."),
            ("Novelty Framing", novelty["novelty_score"], "Measures evidence and clarity in the manuscript, not global originality."),
            ("Writing Quality", writing_score, f"Detected {len(writing['issues'])} rule-based writing issue(s); grammar and spelling are not configured."),
            ("Journal Suitability", scores["journal_suitability"], journal_match["explanation"]),
            ("Formatting Compliance", formatting_score, f"Passed {sum(formatting_checks)} of {len(formatting_checks)} text-based journal checks."),
        ]
    ]
    recommendations = generate_improvements(document_id, document, journal_id=journal_id)["suggestions"]
    recommendations = [
        {
            "category": item["category"],
            "severity": item["severity"],
            "issue": item.get("issue") or item["reason"],
            "explanation": item["reason"],
            "suggested_action": item["suggested"],
            "affected_section": item["section"],
            "priority": item["priority"],
        }
        for item in recommendations
    ]
    return {
        "document_id": document_id,
        "title": "Pre-Submission Readiness Assessment",
        "selected_journal": journal_id,
        "overall_readiness": overall,
        "scores": scores,
        "score_method": "Unweighted arithmetic mean of the nine displayed dimension scores; each dimension is evidence-derived and shown below.",
        "summary": f"Rule-based readiness estimate: {overall}/100. Scores reflect parsed manuscript evidence and configured {journal.get('template_name', journal_id)} checks; they do not predict acceptance.",
        "sections": sections,
        "quality_analysis": quality,
        "research_completeness": completeness,
        "journal_suitability": journal_match,
        "citation_issues": citation_issues,
        "recommendations": sorted(recommendations, key=lambda item: item["priority"]),
        "novelty_scope": "Internal manuscript analysis only; external scholarly similarity search is not configured.",
        "final_checklist": [item["suggested_action"] for item in recommendations],
    }


def _recommendation(category: str, section: str, issue: str, action: str, explanation: str, original: str | None = None) -> dict:
    priority = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}[category]
    return {
        "category": category,
        "severity": category,
        "priority": priority,
        "affected_section": section,
        "issue": issue,
        "suggested_action": action,
        "explanation": explanation,
        "original": original or "No source sentence found; this recommendation concerns missing or inconsistent content.",
    }
