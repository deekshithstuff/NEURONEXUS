import re
from collections.abc import Iterable


CITATION_PATTERNS = [
    ("numeric", re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")),
    ("author_year", re.compile(r"\b([A-Z][A-Za-z-]+(?:\s+et al\.)?)\s*\((\d{4}[a-z]?)\)")),
]


def extract_citations(paragraphs: Iterable[str]) -> list[dict]:
    citations: list[dict] = []
    position = 0
    for para_index, paragraph in enumerate(paragraphs):
        for citation_type, pattern in CITATION_PATTERNS:
            for match in pattern.finditer(paragraph):
                position += 1
                text = match.group(0)
                ref_ids = []
                if citation_type == "numeric":
                    raw = match.group(1)
                    for token in re.split(r"\s*,\s*", raw):
                        if "-" in token:
                            start, end = [int(part.strip()) for part in token.split("-", 1)]
                            ref_ids.extend(str(i) for i in range(start, end + 1))
                        elif token.isdigit():
                            ref_ids.append(token)
                citations.append({
                    "text": text,
                    "citation_type": citation_type,
                    "location": f"paragraph:{para_index + 1}",
                    "position": position,
                    "reference_ids": ref_ids,
                })
    return citations
