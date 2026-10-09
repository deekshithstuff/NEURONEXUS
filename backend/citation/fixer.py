from __future__ import annotations

import copy
import re
from pathlib import Path

from docx import Document

from backend.citation.reference_parser import normalize_doi
from backend.citation.validator import validate_citations, _citation_reference_ids, _reference_key


def suggest_citation_fixes(citations: list[dict], references: list[dict], citation_style: str | None = None) -> dict:
    issues = validate_citations(citations, references, citation_style)
    suggestions = []
    for category, items in issues.items():
        for index, item in enumerate(items):
            action = _action_for(category, item)
            if not action:
                continue
            suggestions.append({
                "id": f"{category}:{index}",
                "category": category,
                "issue": item.get("message"),
                "suggestion": item.get("suggestion") or action["description"],
                "action": action["action"],
                "modifies_original_upload": False,
                "requires_explicit_apply": True,
            })
    return {"issues": issues, "suggestions": suggestions, "source_modified": False}


def apply_citation_fixes(
    analysis: dict,
    *,
    include_uncited_removal: bool = False,
    citation_style: str | None = None,
) -> dict:
    working = copy.deepcopy(analysis)
    citations = list(working.get("citations") or [])
    references = list(working.get("references") or [])

    for reference in references:
        normalized = normalize_doi(reference.get("doi") or _doi_from_text(reference.get("raw_text")))
        if normalized:
            reference["doi"] = normalized
            raw = str(reference.get("raw_text") or "")
            reference["raw_text"] = re.sub(
                r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?10\.\d{4,9}/\S+",
                normalized,
                raw,
                count=1,
                flags=re.I,
            )

    kept: list[dict] = []
    seen_keys: set[str] = set()
    alias: dict[str, str] = {}
    for reference in references:
        key = _reference_key(reference)
        ref_id = str(reference.get("id") or "")
        if key and key in seen_keys:
            previous = next((item["id"] for item in kept if _reference_key(item) == key), None)
            if previous and ref_id:
                alias[ref_id] = str(previous)
            continue
        if key:
            seen_keys.add(key)
        kept.append(reference)
    references = kept
    citations = [_remap_citation(citation, alias) for citation in citations]

    if include_uncited_removal:
        cited = {ref_id for citation in citations for ref_id in _citation_reference_ids(citation)}
        references = [reference for reference in references if str(reference.get("id") or "") in cited]

    numeric = all(str(reference.get("id") or "").isdigit() for reference in references if reference.get("id"))
    if numeric and references:
        old_to_new = {}
        compacted = []
        for index, reference in enumerate(references, start=1):
            old_id = str(reference.get("id") or index)
            old_to_new[old_id] = str(index)
            updated = dict(reference)
            updated["id"] = str(index)
            raw = str(updated.get("raw_text") or "")
            updated["raw_text"] = re.sub(r"^\[?\d+\]?\.?\s*", f"[{index}] ", raw)
            compacted.append(updated)
        references = compacted
        citations = [_remap_citation(citation, old_to_new) for citation in citations]

    working["citations"] = citations
    working["references"] = references
    metadata = dict(working.get("metadata") or {})
    metadata["citation_fixes_applied"] = True
    metadata["uncited_references_removed"] = include_uncited_removal
    working["metadata"] = metadata
    working["citation_check"] = validate_citations(citations, references, citation_style)
    return working


def write_working_docx(source_path: str | Path, destination: str | Path, analysis: dict) -> str:
    source = Path(source_path)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = Document(source)
    replacements = {}
    for citation in analysis.get("citations") or []:
        old = citation.get("original_text")
        new = citation.get("text")
        if old and new and old != new:
            replacements[str(old)] = str(new)
    bibliography = {
        str(reference.get("id")): str(reference.get("raw_text") or "")
        for reference in analysis.get("references") or []
    }
    in_references = False
    for paragraph in document.paragraphs:
        text = paragraph.text
        if text.strip().lower() in {"references", "bibliography"}:
            in_references = True
            continue
        updated = text
        for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace(old, new)
        if in_references:
            match = re.match(r"\[?(\d+)\]?", text.strip())
            if match and match.group(1) in bibliography:
                updated = bibliography[match.group(1)]
        if updated != text and paragraph.runs:
            paragraph.runs[0].text = updated
            for run in paragraph.runs[1:]:
                run.text = ""
        elif updated != text:
            paragraph.text = updated
    document.save(destination)
    return str(destination)


def _remap_citation(citation: dict, mapping: dict[str, str]) -> dict:
    updated = dict(citation)
    original_ids = _citation_reference_ids(citation)
    if original_ids:
        updated.setdefault("original_text", citation.get("text"))
        mapped = [mapping.get(ref_id, ref_id) for ref_id in original_ids]
        updated["reference_ids"] = list(dict.fromkeys(mapped))
        if str(citation.get("citation_type") or "") == "numeric" or re.fullmatch(r"\[.+\]", str(citation.get("text") or "").strip()):
            updated["text"] = "[" + ", ".join(updated["reference_ids"]) + "]"
    return updated


def _doi_from_text(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"10\.\d{4,9}/\S+", raw, re.I)
    return match.group(0) if match else None


def _action_for(category: str, item: dict) -> dict | None:
    actions = {
        "duplicate_references": "merge_duplicate_references",
        "numbering_issues": "compact_numeric_numbering",
        "duplicate_citation_numbers": "remove_repeated_citation_ids",
        "uncited_references": "optional_remove_uncited_references",
        "missing_dois": "normalize_doi_if_present",
        "inconsistent_doi_formatting": "normalize_doi_formatting",
        "inconsistent_title_formatting": "normalize_title_whitespace",
    }
    action = actions.get(category)
    if not action:
        return None
    return {"action": action, "description": item.get("suggestion") or action.replace("_", " ")}
