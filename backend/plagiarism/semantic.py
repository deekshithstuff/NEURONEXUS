"""Compatibility exports for PaperPilot's shared semantic embedding implementation."""

from .semantic_matcher import (
    DEFAULT_MODEL,
    SIMILARITY_THRESHOLD,
    encode_texts,
    semantic_matches,
    semantic_similarity,
    semantic_status,
)

__all__ = [
    "DEFAULT_MODEL",
    "SIMILARITY_THRESHOLD",
    "encode_texts",
    "semantic_matches",
    "semantic_similarity",
    "semantic_status",
]
