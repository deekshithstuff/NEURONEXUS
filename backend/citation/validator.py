import re
from collections import Counter, defaultdict


def validate_citations(citations: list[dict], references: list[dict], citation_style: str | None = None) -> dict:
    ref_ids = [str(ref.get("id") or "").strip() for ref in references]
    ref_lookup = {reference_id: ref for reference_id, ref in zip(ref_ids, references) if reference_id}
    cited_ids = set()
    issues = {
        "missing_references": [],
        "uncited_references": [],
        "duplicate_references": [],
        "numbering_issues": [],
        "duplicate_citation_numbers": [],
        "malformed_references": [],
        "missing_dois": [],
        "style_mismatches": [],
    }

    for citation in citations:
        citation_ids = _citation_reference_ids(citation)
        citation_type = str(citation.get("citation_type") or "").lower()
        if citation_type == "author_year" and not citation_ids:
            citation_ids = _resolve_author_year_reference_ids(citation.get("text"), references)
            if not citation_ids:
                issues["missing_references"].append(_issue(
                    "missing_reference", "high", citation.get("text"),
                    f"Citation {citation.get('text')} has no matching author-year reference.",
                    "Add the complete bibliography entry or correct the citation author/year.",
                ))
        duplicate_ids = [ref_id for ref_id, count in Counter(citation_ids).items() if count > 1]
        for duplicate_id in duplicate_ids:
            issues["duplicate_citation_numbers"].append(_issue(
                "duplicate_citation_number", "medium", citation.get("text"),
                f"Citation {citation.get('text')} repeats reference number [{duplicate_id}].",
                "Remove the repeated number or verify the citation group.",
            ))
        for ref_id in citation_ids:
            cited_ids.add(ref_id)
            if ref_id not in ref_lookup:
                issues["missing_references"].append({
                    **_issue("missing_reference", "high", citation.get("text"),
                             f"Citation [{ref_id}] appears in the manuscript but Reference [{ref_id}] is missing.",
                             f"Add or correct bibliography entry [{ref_id}]."),
                })
        expected_style = _normalized_style(citation_style)
        actual_style = "numeric" if citation_type == "numeric" else "author-year" if citation_type == "author_year" else None
        if expected_style and actual_style and expected_style != actual_style:
            issues["style_mismatches"].append(_issue(
                "citation_style_mismatch", "medium", citation.get("text"),
                f"Citation {citation.get('text')} uses {actual_style} style, while the selected journal profile expects {expected_style}.",
                f"Convert this citation to the selected journal's {expected_style} style after review.",
            ))

    for reference in references:
        ref_id = str(reference.get("id") or "").strip()
        if not ref_id:
            continue
        if ref_id not in cited_ids:
            issues["uncited_references"].append(_issue(
                "uncited_reference", "medium", ref_id,
                f"Reference [{ref_id}] exists but is never cited.",
                f"Cite Reference [{ref_id}] where relevant or remove it after review.",
            ))

    duplicate_ref_ids = [ref_id for ref_id, count in Counter(ref_id for ref_id in ref_ids if ref_id).items() if count > 1]
    for ref_id in duplicate_ref_ids:
        issues["duplicate_citation_numbers"].append(_issue(
            "duplicate_reference_number", "high", ref_id,
            f"More than one bibliography entry is numbered [{ref_id}].",
            "Assign each bibliography entry a unique number and update in-text citations.",
        ))

    seen = defaultdict(list)
    for reference in references:
        key = _reference_key(reference)
        if key:
            seen[key].append(reference)
    for key, group in seen.items():
        if len(group) > 1:
            duplicate_labels = ", ".join("[{}]".format(ref.get("id")) for ref in group)
            issues["duplicate_references"].append({
                "type": "duplicate_reference",
                "severity": "high",
                "citation": ", ".join(str(ref.get("id")) for ref in group),
                "message": f"References {duplicate_labels} appear duplicated by normalized metadata.",
                "suggestion": "Compare the entries and retain one corrected reference if they are duplicates.",
            })

    numeric_reference_ids = [int(ref_id) for ref_id in ref_ids if ref_id.isdigit()]
    if numeric_reference_ids:
        existing = set(numeric_reference_ids)
        for missing_number in sorted(set(range(1, max(existing) + 1)) - existing):
            issues["numbering_issues"].append(_issue(
                "missing_reference_number", "medium", f"[{missing_number}]",
                f"Bibliography numbering has a gap: Reference [{missing_number}] is missing.",
                "Restore the missing reference or renumber the bibliography and in-text citations consistently.",
            ))
        ordered_unique = list(dict.fromkeys(
            ref_id for citation in citations for ref_id in _citation_reference_ids(citation) if ref_id.isdigit()
        ))
        for index, found in enumerate(ordered_unique, start=1):
            if int(found) != index:
                issues["numbering_issues"].append(_issue(
                    "incorrect_citation_order", "medium", f"[{found}]",
                    f"Citation numbering first appears as [{found}] where [{index}] is expected by order of appearance.",
                    "Review first-citation order and renumber references consistently.",
                ))
                break
        for index, reference in enumerate(references, start=1):
            reference_id = str(reference.get("id") or "")
            if reference_id.isdigit() and int(reference_id) != index:
                issues["numbering_issues"].append(_issue(
                    "bibliography_order", "medium", f"[{reference_id}]",
                    f"Reference [{reference_id}] appears at bibliography position {index}.",
                    "Order numeric bibliography entries consistently with the selected citation style.",
                ))

    for reference in references:
        raw = str(reference.get("raw_text") or reference.get("text") or "").strip()
        reference_id = str(reference.get("id") or "?")
        if len(raw) < 15:
            issues["malformed_references"].append(_issue(
                "malformed_reference", "high", reference_id,
                f"Reference [{reference_id}] has too little bibliographic text to validate its structure.",
                "Check that author, title, publication venue, and year or an appropriate publication date are present.",
            ))
            continue
        journal_like = bool(reference.get("venue") or re.search(r"\b(journal|transactions|proceedings|vol\.?|volume)\b", raw, re.I))
        if journal_like and not reference.get("doi"):
            issues["missing_dois"].append(_issue(
                "doi_review", "low", reference_id,
                f"Reference [{reference_id}] appears to describe a journal or proceedings article but has no parsed DOI.",
                "Check the publisher record for a DOI; not every valid reference has one.",
            ))

    return issues


def _issue(issue_type: str, severity: str, citation: str | None, message: str, suggestion: str) -> dict:
    return {"type": issue_type, "severity": severity, "citation": citation, "message": message, "suggestion": suggestion}


def _citation_reference_ids(citation: dict) -> list[str]:
    values = [str(value).strip() for value in citation.get("reference_ids", []) if str(value).strip()]
    if values:
        return values
    match = re.fullmatch(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]", str(citation.get("text") or "").strip())
    if not match:
        return []
    output = []
    for part in re.split(r"\s*,\s*", match.group(1)):
        if "-" in part:
            start, end = (int(value.strip()) for value in part.split("-", 1))
            output.extend(str(value) for value in range(start, end + 1))
        else:
            output.append(part)
    return output


def _normalized_style(style: str | None) -> str | None:
    value = (style or "").lower().replace("_", "-")
    if any(term in value for term in ("numeric", "numbered", "ieee", "vancouver")):
        return "numeric"
    if any(term in value for term in ("author-year", "author year", "apa", "harvard", "acm")):
        return "author-year"
    return None


def _resolve_author_year_reference_ids(citation_text: str | None, references: list[dict]) -> list[str]:
    if not citation_text:
        return []

    year_match = re.search(r"\b(19|20)\d{2}[a-z]?\b", citation_text)
    if not year_match:
        return []

    year = year_match.group(0)
    author_tokens = set()
    for token in re.findall(r"[A-Z][A-Za-z'’.-]+", citation_text):
        if token.lower() in {"et", "al"}:
            continue
        author_tokens.add(_normalize_name(token))

    if not author_tokens:
        return []

    resolved = []
    for reference in references:
        ref_year = str(reference.get("year") or "").strip()
        if ref_year != year:
            continue
        ref_authors = reference.get("authors") or []
        if not ref_authors:
            ref_authors = [str(reference.get("raw_text") or reference.get("title") or "")]
        ref_tokens = set()
        for author in ref_authors:
            for token in re.findall(r"[A-Za-z][A-Za-z'’.-]*", str(author)):
                if token.lower() not in {"et", "al"}:
                    ref_tokens.add(_normalize_name(token))
        if author_tokens & ref_tokens:
            resolved.append(str(reference.get("id")))
    return resolved


def _normalize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z]", "", str(name)).lower()


def _reference_key(reference: dict) -> str | None:
    raw = str(reference.get("raw_text") or reference.get("text") or "")
    doi = str(reference.get("doi") or "").strip().lower()
    if not doi:
        doi_match = re.search(r"10\.\d{4,9}/[^\s]+", raw, re.I)
        doi = doi_match.group(0).rstrip(".,;)").lower() if doi_match else ""
    if doi:
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        doi = re.sub(r"^doi:\s*", "", doi)
        return f"doi:{doi}"
    title = str(reference.get("title") or raw)
    title = re.sub(r"^\s*\[?\d+\]?\.?\s*", "", title)
    title = re.sub(r"\s+", " ", title).strip().lower()
    if title:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", title)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return f"title:{normalized}" if normalized else None
    authors = ", ".join(str(a) for a in reference.get("authors") or [])
    year = str(reference.get("year") or "")
    if authors and year:
        return f"author_year:{authors}:{year}"
    return None
