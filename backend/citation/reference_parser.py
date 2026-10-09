import re


_AUTHOR_SPLIT = re.compile(r"\s+and\s+|;\s+|,\s+(?=[A-Z][a-z]+,)|,\s+(?=[A-Z]\.\s*[A-Z])")


def extract_references(reference_block: str) -> list[dict]:
    if not reference_block:
        return []
    refs = []
    for index, raw in enumerate([line.strip() for line in reference_block.splitlines() if line.strip()], start=1):
        refs.append(parse_reference_line(raw, index))
    return refs


def parse_reference_line(raw: str, index: int) -> dict:
    match = re.match(r"\[?(\d+)\]?\.?\s*(.+)", raw)
    ref_id = match.group(1) if match else str(index)
    text = match.group(2) if match else raw
    year_match = re.search(r"\b((?:19|20)\d{2}[a-z]?)\b", text)
    doi_match = re.search(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s]+)", text, re.I)
    url_match = re.search(r"https?://\S+", text)
    doi = None
    if doi_match:
        doi = normalize_doi(doi_match.group(0))
    title = _extract_title(text)
    authors = _extract_authors(text)
    venue = _extract_venue(text)
    return {
        "id": ref_id,
        "raw_text": raw,
        "authors": authors,
        "title": title,
        "year": year_match.group(1) if year_match else None,
        "venue": venue,
        "volume": None,
        "issue": None,
        "pages": None,
        "doi": doi,
        "url": url_match.group(0).rstrip(".,") if url_match else None,
    }


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip().rstrip(".,;)")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    if not re.match(r"^10\.\d{4,9}/", doi, re.I):
        return None
    return doi.lower()


def _extract_authors(text: str) -> list[str]:
    head = re.split(r"\.\s+|\s+\((?:19|20)\d{2}", text, maxsplit=1)[0]
    if not head or len(head) > 220:
        return []
    parts = [part.strip(" .") for part in _AUTHOR_SPLIT.split(head) if part.strip(" .")]
    authors = []
    for part in parts:
        if part.lower() in {"et al", "et al."}:
            continue
        if re.search(r"\b(journal|proceedings|ieee|acm|elsevier|springer)\b", part, re.I):
            break
        if len(part.split()) <= 6:
            authors.append(part)
    return authors[:8]


def _extract_title(text: str) -> str:
    quoted = re.search(r"[“\"](.+?)[”\"]", text)
    if quoted:
        return quoted.group(1).strip()
    remainder = re.sub(r"^\[?\d+\]?\.?\s*", "", text)
    remainder = re.sub(r"https?://\S+|doi:\s*\S+|10\.\d{4,9}/\S+", "", remainder, flags=re.I)
    parts = [part.strip(" .") for part in remainder.split(".") if part.strip()]
    if len(parts) >= 2:
        return parts[1] if len(parts[1].split()) >= 3 else parts[0]
    return remainder.strip()


def _extract_venue(text: str) -> str | None:
    match = re.search(r"\b(IEEE|ACM|Nature|Springer|Elsevier|Wiley|MDPI|Proceedings|Journal|Transactions)[^.]{0,80}", text, re.I)
    return match.group(0).strip(" .,") if match else None
