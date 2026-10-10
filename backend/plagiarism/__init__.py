"""Plagiarism and text-similarity checking for PaperPilot.

This package compares a manuscript against a clearly identified document
collection, reports matching passages together with their locations, and
separates attributed matches (quotations and cited text) from suspected
unattributed overlap. Semantic similarity is offered only as an optional
signal and never on its own as proof of plagiarism.

The package also exposes modular utilities for preprocessing, exact matching,
lexical scoring, semantic similarity, feature extraction, and classifier
training. These helpers are intentionally lightweight so they work in the
standard project environment without depending on heavy ML libraries that may
not be installed.
"""

from .classifier import PlagiarismClassifier, RuleBasedClassifier, evaluate_classifier, feature_matrix, train_classifier
from .exact_matcher import ExactMatcher, detect_exact_matches
from .feature_extractor import FeatureExtractor, extract_features
from .lexical_matcher import compare_lexical_similarity, lexical_similarity_features
from .preprocessing import normalize_text, normalize_whitespace, sentence_split, split_passages, tokenize
from .scoring import aggregate_scores, classify_similarity, score_similarity
from .semantic_matcher import DEFAULT_MODEL, semantic_matches, semantic_similarity, semantic_status

__all__ = [
    "ExactMatcher",
    "FeatureExtractor",
    "PlagiarismClassifier",
    "RuleBasedClassifier",
    "compare_lexical_similarity",
    "detect_exact_matches",
    "evaluate_classifier",
    "extract_features",
    "feature_matrix",
    "lexical_similarity_features",
    "normalize_text",
    "normalize_whitespace",
    "semantic_matches",
    "semantic_similarity",
    "semantic_status",
    "sentence_split",
    "split_passages",
    "tokenize",
    "train_classifier",
    "score_similarity",
    "classify_similarity",
    "aggregate_scores",
    "DEFAULT_MODEL",
]
