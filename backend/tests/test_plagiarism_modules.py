from __future__ import annotations

import json

import pytest

from backend.plagiarism.classifier import PlagiarismClassifier
from backend.plagiarism.engine import analyze
from backend.plagiarism.exact_matcher import detect_exact_matches
from backend.plagiarism.feature_extractor import FEATURE_NAMES, extract_features
from backend.plagiarism.corpus import corpus_info, load_corpus
from backend.plagiarism.lexical_matcher import (
    TfidfSimilarityIndex,
    char_ngrams,
    lexical_similarity_features,
    word_ngrams,
)
from backend.plagiarism.semantic_matcher import semantic_status
from backend.training.prepare_dataset import load_dataset, prepare_dataset
from backend.training.train_classifier import train_model
from backend.training.evaluate_classifier import evaluate_model_artifact


SOURCE = (
    "Federated learning enables multiple institutions to collaboratively train a shared "
    "prediction model while keeping all training data decentralized."
)
UNRELATED = (
    "Coastal banana orchards require careful irrigation management during dry summer months "
    "to maximize sustainable fruit yields."
)


def _tfidf_vectorizer(*, ngram_range=(1, 2)):
    sklearn_text = pytest.importorskip("sklearn.feature_extraction.text", exc_type=ImportError)
    return sklearn_text.TfidfVectorizer(ngram_range=ngram_range)


def _training_rows(count: int = 60) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        source = f"Source passage group {index} describes federated learning and decentralized data collaboration."
        suspicious = (
            source
            if index % 2 == 0
            else f"Unrelated passage group {index} describes marine biology and coastal ecosystem monitoring."
        )
        rows.append(
            {
                "source_document_id": f"src-{index}",
                "suspicious_document_id": f"sus-{index}",
                "source_text": source,
                "suspicious_text": suspicious,
                "label": 1 if index % 2 == 0 else 0,
                "citation_context": "[1]" if index % 4 == 0 else "",
            }
        )
    return rows


def _write_dataset(path, rows):
    path.write_text(json.dumps({"data": rows}), encoding="utf-8")
    return path


def test_preprocessing_normalizes_text_and_ngram_matchers():
    normalized = __import__("backend.plagiarism.preprocessing", fromlist=["normalize_text"]).normalize_text(
        "  HELLO   WORLD\n\n"
    )
    assert normalized == "hello world"
    assert word_ngrams("red fox runs", 2) == ["red fox", "fox runs"]
    assert len(char_ngrams("abcde", 3)) == 3


def test_exact_matcher_preserves_original_character_offsets():
    source = "Intro: The ﬁnal study evaluates robust federated systems carefully."
    target = "A quotation says the final study evaluates robust federated systems carefully."
    matches = detect_exact_matches(source, target, min_tokens=4, threshold=0.5)
    match = next(item for item in matches if "study evaluates robust federated systems carefully" in str(item["matched_text"]))
    assert source[match["source_start"] : match["source_end"]] == match["matched_text"]
    assert target[match["suspicious_start"] : match["suspicious_end"]].casefold().startswith("the final study")
    assert target[match["suspicious_start"] : match["suspicious_end"]].endswith("carefully")


def test_tfidf_uses_fitted_corpus_vectorizer_and_separate_overlap_features():
    _tfidf_vectorizer()
    index = TfidfSimilarityIndex().fit(
        [
            "apple fruit orchard harvest",
            "automobile engine highway travel",
            "apple orchard irrigation",
        ]
    )
    score = index.similarity("apple orchard", "apple orchard")
    assert score == pytest.approx(1.0)
    features = lexical_similarity_features(
        "apple fruit orchard",
        "apple orchard",
        tfidf_vectorizer=index,
    )
    assert 0 < features["word_overlap"] < 1
    assert 0 < features["tfidf_cosine"] < 1
    assert features["word_overlap"] != features["tfidf_cosine"]
    assert lexical_similarity_features("apple", "apple")["tfidf_cosine"] == 0.0


def test_semantic_missing_dependency_is_explicit_not_hash_fallback(monkeypatch):
    monkeypatch.setattr(
        "backend.plagiarism.semantic_matcher.semantic_status",
        lambda: {"engine": "semantic", "status": "unavailable", "detail": "not installed"},
    )
    status = semantic_status()
    assert status["status"] == "unavailable"
    assert "hash" not in json.dumps(status).lower()
    from backend.plagiarism.semantic_matcher import semantic_similarity

    assert semantic_similarity("source text", "similar target text") is None


def test_semantic_feature_uses_the_configured_model_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.plagiarism.feature_extractor.semantic_status",
        lambda: {"engine": "semantic", "status": "available"},
    )

    def _similarity(_source, _target, *, model_name=None):
        calls.append(model_name)
        return 0.73

    monkeypatch.setattr("backend.plagiarism.feature_extractor.semantic_similarity", _similarity)
    features = extract_features(
        "source text",
        "paraphrased text",
        use_semantic=True,
        semantic_model="verified-model-revision",
    )
    assert features["semantic_cosine"] == pytest.approx(0.73)
    assert calls == ["verified-model-revision"]


def test_missing_semantic_feature_fails_classifier_scoring_explicitly(monkeypatch):
    monkeypatch.setattr(
        "backend.plagiarism.feature_extractor.semantic_status",
        lambda: {"engine": "semantic", "status": "unavailable", "detail": "model unavailable"},
    )
    with pytest.raises(RuntimeError, match="Semantic feature is unavailable"):
        extract_features("source text", "target text", use_semantic=True)


def test_configured_local_corpus_loads_source_metadata(tmp_path, monkeypatch):
    source_file = tmp_path / "licensed-review.txt"
    source_file.write_text(
        "A licensed source passage with enough words to be indexed and compared.",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERPILOT_PLAGIARISM_CORPUS_DIR", str(tmp_path))

    source = next(item for item in load_corpus() if item["id"] == "file-licensed-review")
    status = corpus_info()
    assert source["title"] == "Licensed Review"
    assert source["url"] is None
    assert source["source_type"] == "custom_corpus_file"
    assert status["status"] == "available"
    assert status["custom_source_count"] == 1


def test_invalid_configured_corpus_is_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPILOT_PLAGIARISM_CORPUS_DIR", str(tmp_path / "missing"))
    status = corpus_info()
    assert status["status"] == "failed"
    assert "not accessible" in status["error"]
    with pytest.raises(ValueError, match="not accessible"):
        load_corpus()


def test_empty_corpus_report_discloses_that_no_source_search_occurred():
    report = analyze(
        {"document_id": "DOC-EMPTY-CORPUS", "paragraphs": [SOURCE]},
        [],
        ["lexical"],
    )
    lexical_status = next(engine for engine in report["engines"] if engine["engine"] == "lexical")
    assert lexical_status["status"] == "unavailable"
    assert "no source search was performed" in lexical_status["detail"]
    assert report["scope"]["corpus"]["status"] == "unavailable"


def test_classifier_fit_save_load_and_feature_schema_consistency(tmp_path):
    rows = _training_rows()
    vectorizer = _tfidf_vectorizer(ngram_range=(1, 2)).fit(
        [text for row in rows[:10] for text in (str(row["source_text"]), str(row["suspicious_text"]))]
    )
    features = [
        extract_features(
            str(row["source_text"]),
            str(row["suspicious_text"]),
            citation_context_text=str(row["citation_context"]),
            tfidf_vectorizer=vectorizer,
        )
        for row in rows[:10]
    ]
    classifier = PlagiarismClassifier().fit(
        features,
        [int(row["label"]) for row in rows[:10]],
        tfidf_vectorizer=vectorizer,
    )
    assert list(features[0]) == list(FEATURE_NAMES)
    artifact_path = tmp_path / "model.joblib"
    classifier.save(artifact_path)
    loaded = PlagiarismClassifier.load(artifact_path)
    assert loaded.predict(features) == classifier.predict(features)
    assert loaded.predict_positive_scores(features) == pytest.approx(classifier.predict_positive_scores(features))


def test_classifier_rejects_one_class(tmp_path):
    classifier = PlagiarismClassifier()
    vectorizer = _tfidf_vectorizer().fit(["apple fruit", "coastal orchard"])
    row = extract_features("apple fruit", "apple fruit", tfidf_vectorizer=vectorizer)
    with pytest.raises(ValueError, match="both binary classes"):
        classifier.fit([row, row], [1, 1], tfidf_vectorizer=vectorizer)


def test_classifier_rejects_missing_artifact(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        PlagiarismClassifier.load(tmp_path / "missing.joblib")


def test_insufficient_independent_data_fails_clearly(tmp_path):
    path = _write_dataset(tmp_path / "small.json", _training_rows(8))
    with pytest.raises(ValueError, match="At least 12"):
        prepare_dataset(path)


def test_dataset_split_groups_connected_documents_and_requires_both_classes(tmp_path):
    path = _write_dataset(tmp_path / "pairs.json", _training_rows())
    dataset = prepare_dataset(path, random_state=17)
    splits = [dataset[name] for name in ("train", "validation", "test")]
    assert all({int(row["label"]) for row in split} == {0, 1} for split in splits)
    document_sets = [
        {row["source_document_id"] for row in split}
        | {row["suspicious_document_id"] for row in split}
        for split in splits
    ]
    assert not (document_sets[0] & document_sets[1])
    assert not (document_sets[0] & document_sets[2])
    assert not (document_sets[1] & document_sets[2])
    assert dataset["metadata"]["dataset_version"]
    assert dataset["metadata"]["splits"]["test"]["document_groups"] > 0


def test_dataset_rejects_bad_labels_and_conflicting_duplicates(tmp_path):
    invalid_label = tmp_path / "bad.jsonl"
    invalid_label.write_text(
        json.dumps(
            {
                "source_document_id": "a",
                "suspicious_document_id": "b",
                "source_text": "source",
                "suspicious_text": "target",
                "label": 2,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="binary"):
        load_dataset(invalid_label)

    duplicate = _training_rows(12)
    duplicate[1] = {**duplicate[0], "label": 0}
    with pytest.raises(ValueError, match="Conflicting labels"):
        load_dataset(_write_dataset(tmp_path / "duplicate.json", duplicate))


def test_dataset_rejects_incomplete_rows_instead_of_silently_dropping_them(tmp_path):
    row = {
        "source_document_id": "source-1",
        "suspicious_document_id": "target-1",
        "suspicious_text": "A passage with content.",
        "label": 0,
    }
    with pytest.raises(ValueError, match="missing required fields: source_text"):
        load_dataset(_write_dataset(tmp_path / "missing-field.json", [row]))

    row["source_text"] = " "
    with pytest.raises(ValueError, match="non-empty document IDs and passage texts"):
        load_dataset(_write_dataset(tmp_path / "empty-text.json", [row]))


def test_split_keeps_lightly_edited_derivatives_in_one_group(tmp_path):
    rows = _training_rows()
    base_text = (
        "The research team examined distributed training methods across regional hospitals "
        "while keeping sensitive patient records securely stored within each institution for privacy."
    )
    edited_text = base_text.replace("examined", "evaluated")
    rows[0] = {
        **rows[0],
        "source_text": base_text,
        "suspicious_text": base_text,
    }
    rows[2] = {
        **rows[2],
        "source_text": edited_text,
        "suspicious_text": edited_text,
    }
    prepared = prepare_dataset(_write_dataset(tmp_path / "derivatives.json", rows), random_state=21)
    split_by_document = {
        row["source_document_id"]: name
        for name in ("train", "validation", "test")
        for row in prepared[name]
    }
    assert split_by_document["src-0"] == split_by_document["src-2"]


def test_training_and_evaluation_use_independent_test_split(tmp_path):
    _tfidf_vectorizer()
    dataset_path = _write_dataset(tmp_path / "pairs.json", _training_rows())
    output_dir = tmp_path / "artifacts"
    result = train_model(dataset_path, output_dir=output_dir, random_state=11)
    assert result["model_path"]
    evaluation = evaluate_model_artifact(
        dataset_path,
        result["model_path"],
        random_state=11,
    )
    assert set(evaluation["model"]) == {"accuracy", "precision", "recall", "f1", "confusion_matrix", "false_positive_rate"}
    assert evaluation["test_split"]["examples"] > 0
    assert evaluation["positive_score_calibration"]["is_calibrated"] is False
    assert json.loads((output_dir / "model_metadata.json").read_text(encoding="utf-8"))["evaluation"]


def test_live_engine_returns_classifier_scores_only_for_retrieved_sources(tmp_path, monkeypatch):
    vectorizer = _tfidf_vectorizer(ngram_range=(1, 2)).fit([SOURCE, UNRELATED])
    rows = [
        extract_features(SOURCE, SOURCE, tfidf_vectorizer=vectorizer),
        extract_features(UNRELATED, SOURCE, tfidf_vectorizer=vectorizer),
        extract_features(UNRELATED, UNRELATED, tfidf_vectorizer=vectorizer),
        extract_features(SOURCE, UNRELATED, tfidf_vectorizer=vectorizer),
    ]
    classifier = PlagiarismClassifier(metadata={"dataset_version": "test-data"}).fit(
        rows,
        [1, 1, 0, 0],
        tfidf_vectorizer=vectorizer,
    )
    artifact = tmp_path / "plagiarism_classifier.joblib"
    classifier.save(artifact)
    monkeypatch.setenv("PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH", str(artifact))
    analysis = {
        "document_id": "DOC-LIVE",
        "paragraphs": [SOURCE],
        "citations": [],
        "references": [],
        "sections": [],
    }
    sources = [
        {"id": "real-source", "title": "Source Title", "url": None, "source_type": "test", "authors": [], "year": None, "text": SOURCE},
        {"id": "different-source", "title": "Other Source", "url": None, "source_type": "test", "authors": [], "year": None, "text": UNRELATED},
    ]
    report = analyze(analysis, sources, ["lexical"])
    classifier_output = report["classifier"]
    assert classifier_output["status"]["status"] == "completed"
    assert classifier_output["candidate_scores"]
    assert all(item["source"]["id"] in {"real-source", "different-source"} for item in classifier_output["candidate_scores"])
    assert all("positive_score" in item for item in classifier_output["candidate_scores"])
    assert report["matches"][0]["source"]["id"] == "real-source"


def test_missing_model_is_explicit_and_does_not_change_lexical_matches(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH",
        str(tmp_path / "missing-classifier.joblib"),
    )
    report = analyze(
        {
            "document_id": "DOC-NO-MODEL",
            "paragraphs": [SOURCE],
            "citations": [],
            "references": [],
            "sections": [],
        },
        [
            {
                "id": "identified-source",
                "title": "Identified Source",
                "url": None,
                "source_type": "test",
                "authors": [],
                "year": None,
                "text": SOURCE,
            }
        ],
        ["lexical"],
    )
    assert report["classifier"]["status"]["status"] == "unavailable"
    assert report["classifier"]["candidate_scores"] == []
    assert report["matches"][0]["source"]["id"] == "identified-source"


def test_classifier_semantic_failure_does_not_discard_lexical_results(monkeypatch):
    class _SemanticClassifier:
        tfidf_vectorizer = None
        use_semantic = True
        threshold = 0.5
        metadata = {"semantic_model": "missing-model"}

    monkeypatch.setattr(
        "backend.plagiarism.inference.load_classifier",
        lambda: _SemanticClassifier(),
    )
    monkeypatch.setattr(
        "backend.plagiarism.feature_extractor.semantic_status",
        lambda: {"engine": "semantic", "status": "unavailable", "detail": "model unavailable"},
    )
    report = analyze(
        {
            "document_id": "DOC-SEMANTIC-FAILURE",
            "paragraphs": [SOURCE],
            "citations": [],
            "references": [],
            "sections": [],
        },
        [
            {
                "id": "identified-source",
                "title": "Identified Source",
                "url": None,
                "source_type": "test",
                "authors": [],
                "year": None,
                "text": SOURCE,
            }
        ],
        ["lexical"],
    )
    assert report["classifier"]["status"]["status"] == "failed"
    assert report["classifier"]["candidate_scores"] == []
    assert report["matches"][0]["source"]["id"] == "identified-source"
