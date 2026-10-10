from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PassagePair:
    source_document_id: str
    suspicious_document_id: str
    source_text: str
    suspicious_text: str
    source_start: int | None = None
    source_end: int | None = None
    suspicious_start: int | None = None
    suspicious_end: int | None = None
    citation_context: str | None = None
    label: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimilarityResult:
    method: str
    similarity: float
    score: float
    matched_text: str = ""
    source_start: int | None = None
    source_end: int | None = None
    suspicious_start: int | None = None
    suspicious_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureVector:
    exact_phrase_match: float = 0.0
    word_overlap: float = 0.0
    char_overlap: float = 0.0
    tfidf_cosine: float = 0.0
    semantic_cosine: float = 0.0
    distinctive_phrase_ratio: float = 0.0
    passage_length_ratio: float = 0.0
    citation_context_indicator: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "exact_phrase_match": float(self.exact_phrase_match),
            "word_overlap": float(self.word_overlap),
            "char_overlap": float(self.char_overlap),
            "tfidf_cosine": float(self.tfidf_cosine),
            "semantic_cosine": float(self.semantic_cosine),
            "distinctive_phrase_ratio": float(self.distinctive_phrase_ratio),
            "passage_length_ratio": float(self.passage_length_ratio),
            "citation_context_indicator": int(self.citation_context_indicator),
        }


@dataclass
class ModelArtifact:
    version: str
    model_name: str
    metadata: dict[str, Any]
    threshold: float = 0.5
    feature_names: list[str] = field(default_factory=list)
    random_state: int = 42
