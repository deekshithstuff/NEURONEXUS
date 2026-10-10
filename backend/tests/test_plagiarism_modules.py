from __future__ import annotations

from backend.plagiarism.classifier import PlagiarismClassifier
from backend.plagiarism.exact_matcher import detect_exact_matches
from backend.plagiarism.feature_extractor import extract_features
from backend.plagiarism.preprocessing import normalize_text, tokenize


SOURCE = "Federated learning enables multiple institutions to collaboratively train a shared prediction model while keeping all training data decentralized."
SUSPICIOUS = "Federated learning allows multiple institutions to cooperatively train a shared prediction model while keeping all training data decentralized."


def test_preprocessing_normalizes_text_and_tokens():
    normalized = normalize_text("  HELLO   WORLD\n\n")
    assert normalized == "hello world"
    assert tokenize("hello, world!") == ["hello", "world"]


def test_exact_matcher_detects_overlap():
    matches = detect_exact_matches(SOURCE, SUSPICIOUS, min_tokens=4, threshold=0.5)
    assert matches
    assert matches[0]["matched_tokens"] >= 4


def test_feature_extractor_and_classifier_work_without_sklearn():
    row = extract_features(SOURCE, SUSPICIOUS)
    assert 0.0 <= row["word_overlap"] <= 1.0
    assert 0.0 <= row["tfidf_cosine"] <= 1.0

    classifier = PlagiarismClassifier(threshold=0.5)
    classifier.fit([row, {**row, "exact_phrase_match": 0.0, "word_overlap": 0.0, "tfidf_cosine": 0.0}], [1, 0])
    assert classifier.predict([row, {**row, "exact_phrase_match": 0.0, "word_overlap": 0.0, "tfidf_cosine": 0.0}]) == [1, 0]
