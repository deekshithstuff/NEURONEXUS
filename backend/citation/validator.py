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
        "duplicate_reference_numbers": [],
        "numbering_issues": [],
        "duplicate_citation_numbers": [],
        "malformed_references": [],
        "missing_dois": [],
        "invalid_dois": [],
        "author_year_mismatches": [],
        "references_wrong_order": [],
        "style_mismatches": [],
        "inconsistent_authors": [],
        "inconsistent_years": [],
        "inconsistent_title_formatting": [],
        "inconsistent_doi_formatting": [],
        "invalid_structure": [],
    }

    for citation in citations:
        citation_ids = _citation_reference_ids(citation)
        citation_type = str(citation.get("citation_type") or "").lower()
        if citation_type == "numeric" and not citation_ids:
            issues["numbering_issues"].append(_issue(
                "invalid_numeric_citation", "high", citation.get("text"),
                f"Numeric citation {citation.get('text')} contains an invalid or unsupported reference range.",
                "Check the citation numbers and use an ascending range of at most 1,000 references.",
            ))
        if citation_type == "author_year" and not citation_ids:
            citation_ids = _resolve_author_year_reference_ids(citation.get("text"), references)
            if not citation_ids:
                citation_year = _citation_year(citation.get("text"))
                same_author = [
                    reference for reference in references
                    if _citation_author_tokens(citation.get("text"))
                    & _reference_author_tokens(reference)
                ]
                if same_author and citation_year:
                    available_years = sorted({
                        str(reference.get("year"))
                        for reference in same_author
                        if reference.get("year")
                    })
                    if available_years:
                        issues["author_year_mismatches"].append(_issue(
                            "author_year_mismatch", "high", citation.get("text"),
                            f"Citation {citation.get('text')} has no matching year for the identified author; bibliography years are {', '.join(available_years)}.",
                            "Verify the cited year against the corresponding bibliography entry.",
                        ))
                        continue
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
        issues["duplicate_reference_numbers"].append(_issue(
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
        year = str(reference.get("year") or "")
        doi = str(reference.get("doi") or "")
        authors = _reference_author_tokens(reference)
        title = str(reference.get("title") or "").strip()
        if len(raw) < 15 or len(raw.split()) < 4 or not authors or not title or not (year or doi):
            issues["malformed_references"].append(_issue(
                "malformed_reference", "high", reference_id,
                f"Reference [{reference_id}] is missing enough author, title, year, or DOI information to validate its structure.",
                "Check that author, title, publication venue, and year or an appropriate publication date are present.",
            ))
        doi_match = re.search(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)", raw, re.I)
        if doi and not _is_valid_doi(doi):
            issues["invalid_dois"].append(_issue(
                "invalid_doi", "medium", reference_id,
                f"Reference [{reference_id}] contains a DOI that does not match the expected DOI structure.",
                "Check the DOI against the publisher record and use the DOI identifier without trailing punctuation.",
            ))
        elif re.search(r"\bdoi\b|doi\.org", raw, re.I) and not doi_match:
            issues["invalid_dois"].append(_issue(
                "invalid_doi", "medium", reference_id,
                f"Reference [{reference_id}] includes a DOI label or DOI URL that could not be parsed.",
                "Correct the DOI identifier or remove the malformed DOI text after checking the publisher record.",
            ))
        journal_like = bool(reference.get("venue") or re.search(r"\b(journal|transactions|proceedings|vol\.?|volume)\b", raw, re.I))
        if journal_like and not reference.get("doi"):
            issues["missing_dois"].append(_issue(
                "doi_review", "low", reference_id,
                f"Reference [{reference_id}] appears to describe a journal or proceedings article but has no parsed DOI.",
                "Check the publisher record for a DOI; not every valid reference has one.",
            ))

    expected_style = _normalized_style(citation_style)
    if expected_style == "author-year":
        author_order = [
            _reference_first_author(reference)
            for reference in references
            if _reference_first_author(reference)
        ]
        if author_order != sorted(author_order, key=str.casefold):
            issues["references_wrong_order"].append(_issue(
                "author_year_reference_order", "low", None,
                "The author-year bibliography does not appear to be alphabetized by first author.",
                "Review the bibliography order against the selected profile's author-year reference rules.",
            ))
        for reference in references:
            raw = str(reference.get("raw_text") or reference.get("text") or "").strip()
            reference_id = str(reference.get("id") or "?")
            structure_gaps = []
            if not (reference.get("authors") or re.search(r"[A-Z][a-z]+", raw)):
                structure_gaps.append("author")
            if not (reference.get("title") or len(raw) > 40):
                structure_gaps.append("title")
            if not (reference.get("year") or re.search(r"\b(19|20)\d{2}\b", raw)):
                structure_gaps.append("year")
            if structure_gaps:
                issues["invalid_structure"].append(_issue(
                    "invalid_reference_structure", "high", reference_id,
                    f"Reference [{reference_id}] is missing expected bibliographic fields: {', '.join(structure_gaps)}.",
                    "Complete the author, title, and year fields using the publication record.",
                ))
            doi_raw = str(reference.get("doi") or "")
            if doi_raw and (doi_raw.lower().startswith("http") or doi_raw.lower().startswith("doi:")):
                issues["inconsistent_doi_formatting"].append(_issue(
                    "inconsistent_doi_formatting", "low", reference_id,
                    f"Reference [{reference_id}] stores a DOI with a URL or prefix instead of the canonical 10.xxxx/ form.",
                    "Normalize the DOI to the 10.prefix/suffix form.",
                ))
            title = str(reference.get("title") or "")
            if title and title.isupper() and len(title.split()) > 4:
                issues["inconsistent_title_formatting"].append(_issue(
                    "inconsistent_title_formatting", "low", reference_id,
                    f"Reference [{reference_id}] title appears in all caps.",
                    "Use sentence or title case consistent with the selected bibliography style.",
                ))

    author_forms: dict[str, set[str]] = defaultdict(set)
    years_by_title: dict[str, set[str]] = defaultdict(set)
    for reference in references:
        authors = [str(item).strip() for item in (reference.get("authors") or []) if str(item).strip()]
        if authors:
            family = _normalize_name(authors[0].split()[0])
            if family:
                author_forms[family].add(authors[0])
        title_key = _reference_key(reference) or ""
        year = str(reference.get("year") or "").strip()
        if title_key.startswith("title:") and year:
            years_by_title[title_key].add(year)
    for family, forms in author_forms.items():
        if len(forms) > 1:
            issues["inconsistent_authors"].append(_issue(
                "inconsistent_author_names", "medium", family,
                f"Author name variants appear for '{family}': {', '.join(sorted(forms))}.",
                "Standardize the author name spelling across citations and references.",
            ))
    for title_key, years in years_by_title.items():
        if len(years) > 1:
            issues["inconsistent_years"].append(_issue(
                "inconsistent_year", "medium", title_key,
                f"Similar titles are associated with different years: {', '.join(sorted(years))}.",
                "Confirm the publication year against the publisher record.",
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
            if start < 1 or end < start or end - start > 999:
                return []
            output.extend(str(value) for value in range(start, end + 1))
        else:
            if not part.isdigit() or int(part) < 1:
                return []
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

    year = _citation_year(citation_text)
    if not year:
        return []
    author_tokens = _citation_author_tokens(citation_text)

    if not author_tokens:
        return []

    resolved = []
    for reference in references:
        ref_year = str(reference.get("year") or "").strip()
        if ref_year != year:
            continue
        ref_tokens = _reference_author_tokens(reference)
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


def _citation_year(value: str | None) -> str | None:
    match = re.search(r"\b(?:19|20)\d{2}[a-z]?\b", str(value or ""))
    return match.group(0) if match else None


def _citation_author_tokens(value: str | None) -> set[str]:
    text = str(value or "")
    author_part = re.sub(r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)", "", text)
    author_part = re.sub(r"\b(?:19|20)\d{2}[a-z]?\b", "", author_part)
    return {
        _normalize_name(token)
        for token in re.findall(r"[A-Za-z][A-Za-z'’.-]*", author_part)
        if token.lower() not in {"et", "al"}
    }


def _reference_author_tokens(reference: dict) -> set[str]:
    authors = reference.get("authors") or []
    if not authors:
        raw = str(reference.get("raw_text") or reference.get("title") or "")
        year_match = re.search(r"\b(?:19|20)\d{2}[a-z]?\b", raw)
        author_text = raw[:year_match.start()] if year_match else raw.split(".", 1)[0]
        authors = [re.sub(r"^\s*\[?\d+\]?[.)]?\s*", "", author_text)]
    tokens: set[str] = set()
    for author in authors:
        for token in re.findall(r"[A-Za-z][A-Za-z'’.-]*", str(author)):
            if token.lower() not in {"et", "al", "and"}:
                normalized = _normalize_name(token)
                if normalized:
                    tokens.add(normalized)
    return tokens


def _reference_first_author(reference: dict) -> str:
    tokens = _reference_author_tokens(reference)
    return sorted(tokens, key=lambda value: (-len(value), value))[0] if tokens else ""


def _is_valid_doi(value: str) -> bool:
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value.strip(), flags=re.I)
    normalized = re.sub(r"^doi:\s*", "", normalized, flags=re.I).rstrip(".,;)")
    return bool(re.fullmatch(r"10\.\d{4,9}/\S+", normalized, re.I))
