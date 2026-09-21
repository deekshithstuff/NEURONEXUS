from .validator import validate_citations


def detect_duplicates(citations: list[dict], references: list[dict]) -> list[dict]:
    return validate_citations(citations, references)["duplicate_references"]
