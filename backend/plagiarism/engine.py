"""Deterministic lexical matching engine.

The engine compares manuscript sentences against an identified corpus using a
token-level sequence matcher. It reports the location of every matching passage
and separates attributed overlap (quotations and cited text) from suspected
unattributed overlap. It never invents sources: a match is only reported when a
real corpus sentence shares a run of words with the manuscript.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

from backend.citation.validator import validate_citations

from .corpus import corpus_info
from .text import (
    has_citation,
    is_fully_quoted,
    normalize_whitespace,
    quotation_spans,
    span_within,
    split_sentences,
    tokenize,
    word_count,
)

MIN_MATCH_WORDS = 8
MIN_COVERAGE = 0.5
EXACT_COVERAGE = 0.9
NEAR_EXACT_RATIO = 0.75
MIN_CANDIDATE_OVERLAP = 4
MAX_CANDIDATES = 200

BOILERPLATE_PHRASES = {
    "all rights reserved",
    "this page intentionally left blank",
    "table of contents",
    "conflict of interest",
    "the authors declare no competing interests",
    "author contributions",
    "supplementary material",
    "corresponding author",
}

MATCH_NOTES = {
    "suspected_unattributed": "This passage overlaps an identified source and has no nearby in-text citation.",
    "cited_match": "This passage overlaps an identified source and includes an in-text citation.",
    "quotation": "This passage is enclosed in quotation marks but has no nearby in-text citation.",
    "attributed_quotation": "This passage is quoted and accompanied by an in-text citation.",
    "semantic_related": "This passage is semantically similar to an identified source; semantics alone are not evidence of plagiarism.",
    "external_match": "This match was reported by the external comparison provider and must be verified against the original source.",
}


def extract_manuscript_passages(analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    paragraphs = analysis.get("paragraphs") or []
    sections = analysis.get("sections") or []
    normalized_sections = [
        (normalize_whitespace(section.get("content") or ""), section) for section in sections
    ]
    passages: list[dict[str, Any]] = []
    excluded = {"references_words": 0, "boilerplate_passages": 0}
    citation_paragraphs = _citation_paragraphs(analysis)
    for paragraph_index, paragraph in enumerate(paragraphs):
        section = _section_for_paragraph(paragraph, normalized_sections)
        section_type = (section or {}).get("type") or "other"
        section_heading = (section or {}).get("heading") or ""
        if section_type == "references":
            excluded["references_words"] += word_count(paragraph)
            continue
        quote_spans = quotation_spans(paragraph)
        paragraph_has_citation = (paragraph_index + 1) in citation_paragraphs
        for sentence_index, (sentence, start, end) in enumerate(split_sentences(paragraph)):
            tokens = tokenize(sentence)
            if len(tokens) < 3:
                continue
            if _is_boilerplate(sentence):
                excluded["boilerplate_passages"] += 1
                continue
            quoted = span_within(quote_spans, start, end) or is_fully_quoted(sentence)
            attributed = has_citation(sentence) or (quoted and paragraph_has_citation)
            passages.append(
                {
                    "paragraph_index": paragraph_index,
                    "paragraph_number": paragraph_index + 1,
                    "sentence_index": sentence_index,
                    "text": sentence,
                    "char_start": start,
                    "char_end": end,
                    "tokens": tokens,
                    "section_heading": section_heading,
                    "section_type": section_type,
                    "quoted": quoted,
                    "attributed": attributed,
                }
            )
    return passages, excluded


def _citation_paragraphs(analysis: dict[str, Any]) -> set[int]:
    paragraphs: set[int] = set()
    for citation in analysis.get("citations") or []:
        match = re.match(r"paragraph:(\d+)", str(citation.get("location") or ""))
        if match:
            paragraphs.add(int(match.group(1)))
    return paragraphs


def _section_for_paragraph(paragraph: str, normalized_sections: list[tuple[str, dict]]) -> dict | None:
    target = normalize_whitespace(paragraph)
    if not target:
        return None
    for content, section in normalized_sections:
        if content and target in content:
            return section
    for _, section in normalized_sections:
        if normalize_whitespace(section.get("heading") or "") == target:
            return section
    return None


def _is_boilerplate(sentence: str) -> bool:
    normalized = normalize_whitespace(sentence).lower().strip(" .:")
    return normalized in BOILERPLATE_PHRASES


def index_corpus(sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, set[int]]]:
    inverted: dict[str, set[int]] = defaultdict(set)
    sentences: list[dict[str, Any]] = []
    for source in sources:
        for text, _, _ in split_sentences(source.get("text") or ""):
            tokens = tokenize(text)
            if len(tokens) < MIN_MATCH_WORDS:
                continue
            index = len(sentences)
            sentences.append({"source": source, "text": text, "tokens": tokens})
            for token in set(tokens):
                inverted[token].add(index)
    return sentences, inverted


def _candidate_indices(tokens: list[str], inverted: dict[str, set[int]]) -> list[int]:
    counts: Counter[int] = Counter()
    for token in set(tokens):
        for index in inverted.get(token, ()):
            counts[index] += 1
    return [index for index, count in counts.most_common(MAX_CANDIDATES) if count >= MIN_CANDIDATE_OVERLAP]


def match_passages(
    passages: list[dict[str, Any]],
    corpus_sentences: list[dict[str, Any]],
    inverted: dict[str, set[int]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for passage in passages:
        tokens = passage["tokens"]
        if len(tokens) < MIN_MATCH_WORDS:
            continue
        best: dict[str, Any] | None = None
        matcher: SequenceMatcher | None = None
        for candidate in _candidate_indices(tokens, inverted):
            corpus_sentence = corpus_sentences[candidate]
            current = SequenceMatcher(None, tokens, corpus_sentence["tokens"], autojunk=False)
            matched = sum(block.size for block in current.get_matching_blocks())
            if matched < MIN_MATCH_WORDS:
                continue
            coverage = matched / len(tokens)
            ratio = current.ratio()
            qualifies = coverage >= MIN_COVERAGE and (coverage >= EXACT_COVERAGE or ratio >= NEAR_EXACT_RATIO)
            if not qualifies:
                continue
            if best is None or matched > best["matched_words"]:
                best = {
                    "source_sentence": corpus_sentence,
                    "matched_words": matched,
                    "coverage": coverage,
                    "ratio": ratio,
                }
                matcher = current
        if best is not None:
            matches.append(_build_match(passage, best))
    return matches


def _build_match(passage: dict[str, Any], best: dict[str, Any]) -> dict[str, Any]:
    source = best["source_sentence"]["source"]
    method = "exact" if best["coverage"] >= EXACT_COVERAGE else "near_exact"
    classification = _classification(passage)
    return {
        "passage": passage["text"],
        "location": {
            "paragraph_index": passage["paragraph_index"],
            "paragraph_number": passage["paragraph_number"],
            "sentence_index": passage["sentence_index"],
            "section_heading": passage["section_heading"],
            "section_type": passage["section_type"],
            "char_start": passage["char_start"],
            "char_end": passage["char_end"],
        },
        "source": {
            "id": source["id"],
            "title": source["title"],
            "url": source["url"],
            "source_type": source["source_type"],
            "authors": source["authors"],
            "year": source["year"],
        },
        "method": method,
        "similarity": round(best["ratio"], 4),
        "coverage": round(best["coverage"], 4),
        "matched_words": best["matched_words"],
        "attributed": bool(passage["attributed"]),
        "quoted": bool(passage["quoted"]),
        "classification": classification,
        "matched_text": best["source_sentence"]["text"],
        "note": MATCH_NOTES[classification],
    }


def _classification(passage: dict[str, Any]) -> str:
    if passage["quoted"] and passage["attributed"]:
        return "attributed_quotation"
    if passage["quoted"]:
        return "quotation"
    if passage["attributed"]:
        return "cited_match"
    return "suspected_unattributed"


def build_report(
    *,
    document_id: str,
    provider: str,
    matches: list[dict[str, Any]],
    total_words: int,
    excluded: dict[str, int],
    engine_status: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    citation_style: str | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    numbered = _number_matches(matches)
    source_summary = _source_summary(numbered)
    matched_words = sum(match["matched_words"] for match in numbered)
    suspected = [match for match in numbered if match["classification"] == "suspected_unattributed"]
    quotations = [match for match in numbered if match["classification"] in {"quotation", "attributed_quotation"}]
    cited = [match for match in numbered if match["classification"] == "cited_match"]
    suspected_words = sum(match["matched_words"] for match in suspected)
    summary = {
        "overall_similarity": round(matched_words / total_words, 4) if total_words else 0.0,
        "matched_words": matched_words,
        "total_words": total_words,
        "match_count": len(numbered),
        "source_count": len(source_summary),
        "suspected_unattributed_words": suspected_words,
        "suspected_unattributed_ratio": round(suspected_words / total_words, 4) if total_words else 0.0,
        "attributed_match_count": len(cited),
        "quotation_match_count": len(quotations),
    }
    warnings = _citation_warnings(analysis or {}, suspected, quotations, citation_style)
    return {
        "document_id": document_id,
        "provider": provider,
        "engines": engine_status,
        "summary": summary,
        "sources": source_summary,
        "matches": numbered,
        "citation_warnings": warnings,
        "exclusions": {
            "references_words_excluded": excluded.get("references_words", 0),
            "boilerplate_passages_excluded": excluded.get("boilerplate_passages", 0),
            "quoted_passages_retained": len(quotations),
            "notes": [
                "The reference list is excluded from similarity scoring.",
                "Short and boilerplate phrases are excluded from matching.",
                "Quoted passages are reported but counted as attributed matching text.",
            ],
        },
        "scope": {
            "corpus": corpus_info(sources),
            "engines": [engine["engine"] for engine in engine_status],
            "limitations": [
                "A match indicates textual overlap with one identified corpus source only.",
                "Semantic similarity signals topical or paraphrase similarity and is not evidence of plagiarism on its own.",
                "This check does not prove plagiarism; verify every match against the original source.",
                "Standard terminology and journal template text are excluded or flagged transparently.",
            ],
        },
        "disclaimer": (
            "Similarity is not a verdict. Overlap with a source is not proof of plagiarism; "
            "review attributed quotations, common phrases, and cited material carefully."
        ),
    }


def _number_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {
        "suspected_unattributed": 0,
        "external_match": 1,
        "quotation": 2,
        "cited_match": 3,
        "attributed_quotation": 4,
        "semantic_related": 5,
    }
    ordered = sorted(
        matches,
        key=lambda match: (order.get(match["classification"], 5), -match["matched_words"], match["location"]["paragraph_number"]),
    )
    numbered = []
    for index, match in enumerate(ordered, start=1):
        numbered.append({**match, "id": f"PM-{index:04d}"})
    return numbered


def _source_summary(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for match in matches:
        source = match["source"]
        entry = totals.setdefault(
            source["id"],
            {
                "id": source["id"],
                "title": source["title"],
                "url": source["url"],
                "source_type": source["source_type"],
                "authors": source["authors"],
                "year": source["year"],
                "matched_words": 0,
                "passage_count": 0,
                "max_similarity": 0.0,
            },
        )
        entry["matched_words"] += match["matched_words"]
        entry["passage_count"] += 1
        entry["max_similarity"] = max(entry["max_similarity"], match["similarity"])
    return sorted(totals.values(), key=lambda entry: (-entry["matched_words"], entry["id"]))


def _citation_warnings(
    analysis: dict[str, Any],
    suspected: list[dict[str, Any]],
    quotations: list[dict[str, Any]],
    citation_style: str | None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    issues = validate_citations(analysis.get("citations") or [], analysis.get("references") or [], citation_style)
    for issue_type, values in issues.items():
        for issue in values:
            warnings.append(
                {
                    "type": issue_type,
                    "severity": issue.get("severity", "medium"),
                    "citation": issue.get("citation"),
                    "message": issue.get("message"),
                    "suggestion": issue.get("suggestion"),
                }
            )
    for match in suspected:
        location = match["location"]
        section = location["section_heading"] or "body"
        warnings.append(
            {
                "type": "match_without_citation",
                "severity": "high",
                "citation": None,
                "message": (
                    f"Paragraph {location['paragraph_number']} in '{section}' overlaps "
                    f"'{match['source']['title']}' without an in-text citation."
                ),
                "suggestion": "Add an in-text citation for the source or rewrite the passage in your own words.",
            }
        )
    for match in quotations:
        location = match["location"]
        warnings.append(
            {
                "type": "quotation_without_citation",
                "severity": "medium",
                "citation": None,
                "message": (
                    f"Quoted passage in paragraph {location['paragraph_number']} overlaps "
                    f"'{match['source']['title']}' but has no nearby citation."
                ),
                "suggestion": "Add a citation for the quoted source or confirm the quotation is common knowledge.",
            }
        )
    return warnings


def analyze(
    analysis: dict[str, Any],
    sources: list[dict[str, Any]],
    engines: list[str] | None = None,
    citation_style: str | None = None,
) -> dict[str, Any]:
    engines = engines or []
    document_id = analysis.get("document_id") or ""
    passages, excluded = extract_manuscript_passages(analysis)
    total_words = sum(len(passage["tokens"]) for passage in passages)
    corpus_sentences, inverted = index_corpus(sources)
    matches = match_passages(passages, corpus_sentences, inverted)
    engine_status: list[dict[str, Any]] = [
        {
            "engine": "lexical",
            "status": "completed",
            "detail": "Exact and near-exact sentence matching against the identified corpus.",
        }
    ]
    if "semantic" in engines:
        from . import semantic

        semantic_matches, status = semantic.semantic_matches(passages, matches, corpus_sentences)
        matches.extend(semantic_matches)
        engine_status.append(status)
    return build_report(
        document_id=document_id,
        provider="internal",
        matches=matches,
        total_words=total_words,
        excluded=excluded,
        engine_status=engine_status,
        sources=sources,
        citation_style=citation_style,
        analysis=analysis,
    )
