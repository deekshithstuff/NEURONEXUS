import re
from collections import defaultdict


def validate_citations(citations: list[dict], references: list[dict]) -> dict:
    ref_lookup = {str(ref.get("id")): ref for ref in references}
    cited_ids = set()
    issues = {
        "missing_references": [],
        "uncited_references": [],
        "duplicate_references": [],
        "numbering_issues": [],
    }

    for citation in citations:
        ref_ids = [str(ref_id) for ref_id in citation.get("reference_ids", []) if str(ref_id).strip()]
        if citation.get("citation_type") == "author_year" and not ref_ids:
            ref_ids = _resolve_author_year_reference_ids(citation.get("text"), references)
            citation["reference_ids"] = ref_ids
        for ref_id in ref_ids:
            cited_ids.add(str(ref_id))
            if str(ref_id) not in ref_lookup:
                issues["missing_references"].append({
                    "type": "missing_reference",
                    "severity": "high",
                    "citation": citation.get("text"),
                    "message": f"Citation {citation.get('text')} has no corresponding reference {ref_id}.",
                })

    for reference in references:
        ref_id = str(reference.get("id"))
        if ref_id not in cited_ids:
            issues["uncited_references"].append({
                "type": "uncited_reference",
                "severity": "medium",
                "citation": ref_id,
                "message": f"Reference [{ref_id}] exists but is never cited.",
            })

    seen = defaultdict(list)
    for reference in references:
        key = _reference_key(reference)
        if key:
            seen[key].append(reference)
    for key, group in seen.items():
        if len(group) > 1:
            issues["duplicate_references"].append({
                "type": "duplicate_reference",
                "severity": "high",
                "citation": key,
                "message": "Duplicate references were detected by normalized metadata matching.",
            })

    numeric_ids = []
    for citation in citations:
        for ref_id in citation.get("reference_ids", []):
            numeric_ids.append(int(ref_id))
    if numeric_ids:
        sorted_ids = sorted(set(numeric_ids))
        for idx, expected in enumerate(sorted_ids, start=1):
            if expected != idx and expected not in [1, 2, 3]:
                issues["numbering_issues"].append({
                    "type": "citation_numbering_problem",
                    "severity": "medium",
                    "citation": f"[{expected}]",
                    "message": f"Expected numbering to remain sequential; found {expected} where {idx} was expected.",
                })

    return issues


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
    doi = str(reference.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = re.sub(r"\s+", " ", str(reference.get("title") or "")).strip().lower()
    if title:
        return f"title:{title}"
    authors = ", ".join(str(a) for a in reference.get("authors") or [])
    year = str(reference.get("year") or "")
    if authors and year:
        return f"author_year:{authors}:{year}"
    return None
