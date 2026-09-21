import re


def extract_references(reference_block: str) -> list[dict]:
    if not reference_block:
        return []
    refs = []
    for index, raw in enumerate([line.strip() for line in reference_block.splitlines() if line.strip()], start=1):
        match = re.match(r"\[?(\d+)\]?\.?\s*(.+)", raw)
        ref_id = match.group(1) if match else str(index)
        text = match.group(2) if match else raw
        year = (re.search(r"\b(19|20)\d{2}[a-z]?\b", text) or [None])[0]
        doi_match = re.search(r"10\.\d{4,9}/\S+", text, re.I)
        url_match = re.search(r"https?://\S+", text)
        refs.append({
            "id": ref_id,
            "raw_text": raw,
            "authors": [],
            "title": text,
            "year": year,
            "venue": None,
            "volume": None,
            "issue": None,
            "pages": None,
            "doi": doi_match.group(0).rstrip(".,") if doi_match else None,
            "url": url_match.group(0).rstrip(".,") if url_match else None,
        })
    return refs
