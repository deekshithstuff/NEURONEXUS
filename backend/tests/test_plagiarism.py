from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.database import connection
from backend.main import app
from backend.plagiarism.corpus import load_corpus
from backend.plagiarism.engine import analyze, build_report
from backend.plagiarism.external import ExternalScanError, _normalize_result

client = TestClient(app)

COPILED_SENTENCE = (
    "Federated learning enables multiple institutions to collaboratively train a shared "
    "prediction model while keeping all training data decentralized."
)
PARAPHRASED_SENTENCE = (
    "Federated learning allows many institutions to cooperatively train a shared prediction "
    "model while maintaining all training data decentralized."
)
ORIGINAL_SENTENCE = (
    "Banana orchards in coastal regions require careful irrigation management during dry "
    "summer months to maximize sustainable yields."
)

CORPUS = [
    {
        "id": "src-1",
        "title": "Source One",
        "authors": ["A. Author"],
        "year": "2020",
        "url": None,
        "source_type": "test",
        "text": COPILED_SENTENCE,
    }
]


def _analysis(paragraphs, citations=None, references=None, sections=None):
    return {
        "document_id": "DOC-UNIT",
        "paragraphs": paragraphs,
        "citations": citations or [],
        "references": references or [],
        "sections": sections or [],
    }


def test_engine_detects_exact_matches_and_ignores_original_text():
    exact = analyze(_analysis([COPILED_SENTENCE]), CORPUS, ["lexical"])
    assert exact["summary"]["match_count"] == 1
    assert exact["matches"][0]["method"] == "exact"
    assert exact["matches"][0]["classification"] == "suspected_unattributed"
    assert exact["summary"]["suspected_unattributed_words"] > 0

    original = analyze(_analysis([ORIGINAL_SENTENCE]), CORPUS, ["lexical"])
    assert original["summary"]["match_count"] == 0
    assert original["summary"]["overall_similarity"] == 0.0


def test_engine_detects_lightly_edited_passage_as_near_exact():
    report = analyze(_analysis([PARAPHRASED_SENTENCE]), CORPUS, ["lexical"])
    assert report["summary"]["match_count"] == 1
    assert report["matches"][0]["method"] == "near_exact"


def test_engine_does_not_flag_common_short_boilerplate():
    boilerplate = "All rights reserved."
    report = analyze(_analysis([boilerplate]), [{**CORPUS[0], "text": boilerplate}], ["lexical"])
    assert report["summary"]["match_count"] == 0
    assert report["exclusions"]["boilerplate_passages_excluded"] == 1


def test_semantic_paraphrase_is_reported_separately_from_textual_overlap(monkeypatch):
    np = pytest.importorskip("numpy")
    paraphrase = (
        "Institutions can jointly develop predictive models while each organization retains "
        "custody of its own private records."
    )

    def _encode(texts, *, model_name=None):
        return np.tile(np.array([[1.0, 0.0]]), (len(texts), 1))

    monkeypatch.setattr(
        "backend.plagiarism.semantic_matcher.semantic_status",
        lambda: {"engine": "semantic", "status": "available", "model": "test-model"},
    )
    monkeypatch.setattr("backend.plagiarism.semantic_matcher.encode_texts", _encode)
    report = analyze(_analysis([paraphrase]), CORPUS, ["lexical", "semantic"])

    assert report["summary"]["overall_similarity"] == 0.0
    semantic_matches = [match for match in report["matches"] if match["classification"] == "semantic_related"]
    assert semantic_matches
    assert semantic_matches[0]["matched_words"] == 0
    assert "not textual overlap or plagiarism" in semantic_matches[0]["note"]
    assert len(report["match_groups"]["semantic"]) == len(semantic_matches)
    assert report["summary"]["semantic_match_count"] == len(semantic_matches)


def test_engine_treats_cited_quotation_as_attributed():
    citation = {
        "text": "[1]",
        "citation_type": "numeric",
        "location": "paragraph:1",
        "position": 1,
        "reference_ids": ["1"],
    }
    reference = {"id": "1", "raw_text": "[1] A. Author. Source One. Journal, 2020. doi:10.1/x"}
    report = analyze(
        _analysis([f'"{COPILED_SENTENCE}"'], citations=[citation], references=[reference]),
        CORPUS,
        ["lexical"],
    )
    match = report["matches"][0]
    assert match["quoted"] is True
    assert match["attributed"] is True
    assert match["classification"] == "attributed_quotation"
    assert report["summary"]["suspected_unattributed_words"] == 0


def test_engine_excludes_reference_list_text():
    section = {
        "section_id": "SEC-01",
        "heading": "References",
        "type": "references",
        "position": 1,
        "content": COPILED_SENTENCE,
    }
    report = analyze(_analysis([COPILED_SENTENCE], sections=[section]), CORPUS, ["lexical"])
    assert report["summary"]["match_count"] == 0
    assert report["exclusions"]["references_words_excluded"] > 0


def test_external_provider_matches_are_separate_from_local_similarity():
    provider = _normalize_result(
        {
            "results": [
                {
                    "matchedText": "A provider-reported passage.",
                    "sourceText": "A source passage.",
                    "matchedWords": 3,
                    "score": 0.4,
                    "source": {"id": "external-source-1", "title": "External Source"},
                }
            ]
        },
        "copyleaks",
    )
    report = build_report(
        document_id="DOC-EXTERNAL",
        provider=provider["provider"],
        matches=provider["matches"],
        total_words=10,
        excluded={},
        engine_status=[{"engine": "external:copyleaks", "status": "completed"}],
        sources=[],
    )
    assert report["match_groups"]["external"] == report["matches"]
    assert report["summary"]["external_match_count"] == 1
    assert report["summary"]["overall_similarity"] == 0.0
    assert report["summary"]["matched_words"] == 0


def test_engine_handles_empty_document():
    report = analyze(_analysis([]), CORPUS, ["lexical"])
    assert report["summary"]["total_words"] == 0
    assert report["summary"]["overall_similarity"] == 0.0
    assert report["matches"] == []


def _register(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"name": "Plagiarism Tester", "email": f"plagiarism-{uuid4()}@example.test", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _build_docx(path: Path, paragraphs: list[str], references: list[str] | None = None, title: str = "Similarity Test") -> None:
    document = Document()
    document.add_heading(title, level=1)
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if references:
        document.add_heading("References", level=1)
        for reference in references:
            document.add_paragraph(reference)
    document.save(path)


def _upload_and_analyze(client: TestClient, headers: dict, tmp_path: Path, paragraphs, references=None) -> str:
    path = tmp_path / f"manuscript-{uuid4().hex[:6]}.docx"
    _build_docx(path, paragraphs, references)
    with path.open("rb") as handle:
        upload = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": (path.name, handle, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["document_id"]
    analyzed = client.post(f"/api/documents/{document_id}/analyze", headers=headers, json={})
    assert analyzed.status_code == 200, analyzed.text
    return document_id


def _wait_for_scan(client: TestClient, headers: dict, scan_id: str, attempts: int = 200) -> dict:
    for _ in range(attempts):
        payload = client.get(f"/api/plagiarism/scans/{scan_id}", headers=headers).json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("scan did not reach a terminal state in time")


def test_plagiarism_scan_reports_matches_and_citation_warning(tmp_path, monkeypatch):
    with TestClient(app) as session:
        headers = _register(session)
        monkeypatch.setenv(
            "PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH",
            str(tmp_path / "classifier-not-installed.joblib"),
        )
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])

        started = session.post(
            f"/api/documents/{document_id}/plagiarism/scan",
            headers=headers,
            json={"engines": ["lexical"], "provider": "internal"},
        )
        assert started.status_code == 200, started.text
        scan = _wait_for_scan(session, headers, started.json()["scan_id"])
        assert scan["status"] == "completed", scan
        report = scan["report"]
        assert report["provider"] == "internal"
        assert report["summary"]["match_count"] >= 1
        assert report["summary"]["overall_similarity"] > 0
        assert any(match["method"] == "exact" for match in report["matches"])
        assert any(warning["type"] == "match_without_citation" for warning in report["citation_warnings"])
        assert report["scope"]["corpus"]["source_count"] >= 1
        assert report["classifier"]["status"]["status"] == "unavailable"
        assert report["classifier"]["candidate_scores"] == []
        assert next(engine for engine in report["engines"] if engine["engine"] == "lexical")["status"] == "completed"

        listing = session.get(f"/api/documents/{document_id}/plagiarism/scans", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["scans"][0]["scan_id"] == scan["scan_id"]

        download = session.get(f"/api/plagiarism/scans/{scan['scan_id']}/download", headers=headers)
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]


def test_internal_api_scan_attaches_scores_from_loaded_classifier(tmp_path, monkeypatch):
    class _LoadedClassifier:
        tfidf_vectorizer = None
        use_semantic = False
        threshold = 0.5
        metadata = {"dataset_version": "test-fixture"}

        def predict_positive_scores(self, features):
            return [0.9] * len(features)

        def predict(self, features):
            return [1] * len(features)

    monkeypatch.setattr(
        "backend.plagiarism.inference.load_classifier",
        lambda: _LoadedClassifier(),
    )
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])
        started = session.post(
            f"/api/documents/{document_id}/plagiarism/scan",
            headers=headers,
            json={"provider": "internal", "engines": ["lexical"]},
        )
        scan = _wait_for_scan(session, headers, started.json()["scan_id"])

    assert scan["status"] == "completed"
    classifier = scan["report"]["classifier"]
    assert classifier["status"]["status"] == "completed"
    assert classifier["candidate_scores"]
    corpus_ids = {source["id"] for source in load_corpus()}
    assert {item["source"]["id"] for item in classifier["candidate_scores"]} <= corpus_ids
    assert any(match["method"] == "exact" for match in scan["report"]["matches"])


def test_plagiarism_scan_without_citation_can_be_downloaded_as_report(tmp_path):
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [ORIGINAL_SENTENCE])
        started = session.post(f"/api/documents/{document_id}/plagiarism/scan", headers=headers, json={})
        scan = _wait_for_scan(session, headers, started.json()["scan_id"])
        assert scan["status"] == "completed"
        assert scan["report"]["summary"]["match_count"] == 0


def test_empty_document_scan_completes_without_matches(tmp_path):
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, ["   "])
        started = session.post(f"/api/documents/{document_id}/plagiarism/scan", headers=headers, json={})
        scan = _wait_for_scan(session, headers, started.json()["scan_id"])
        assert scan["status"] == "completed"
        assert scan["report"]["summary"]["match_count"] == 0


def test_scan_before_analysis_is_rejected():
    with TestClient(app) as session:
        headers = _register(session)
        user_id = session.get("/api/auth/me", headers=headers).json()["user"]["id"]
        document_id = f"DOC-{uuid4().hex[:8].upper()}"
        with connection() as conn:
            conn.execute(
                "INSERT INTO documents (id, user_id, filename, original_path, status) VALUES (?, ?, ?, ?, ?)",
                (document_id, user_id, "raw.docx", "", "uploaded"),
            )
        response = session.post(f"/api/documents/{document_id}/plagiarism/scan", headers=headers, json={})
        assert response.status_code == 400
        assert "analyze" in response.json()["detail"].lower()


def test_plagiarism_endpoints_require_authentication(tmp_path):
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])
        assert session.get("/api/plagiarism/status").status_code == 401
        assert session.post(f"/api/documents/{document_id}/plagiarism/scan", json={}).status_code == 401

        other = _register(session)
        assert session.get(f"/api/documents/{document_id}/plagiarism/scans", headers=other).status_code == 404
        started = session.post(f"/api/documents/{document_id}/plagiarism/scan", headers=headers, json={})
        scan_id = started.json()["scan_id"]
        assert session.get(f"/api/plagiarism/scans/{scan_id}", headers=other).status_code == 404


def test_invalid_file_upload_is_rejected():
    with TestClient(app) as session:
        headers = _register(session)
        response = session.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("notes.txt", BytesIO(b"just text"), "text/plain")},
        )
        assert response.status_code == 400
        corrupt = session.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("broken.docx", BytesIO(b"not a zip"), "application/octet-stream")},
        )
        assert corrupt.status_code == 400


def test_external_provider_failure_is_reported_without_fabricated_matches(tmp_path, monkeypatch):
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])
        monkeypatch.setenv("PAPERPILOT_PLAGIARISM_PROVIDER", "copyleaks")
        monkeypatch.setenv("COPYLEAKS_EMAIL", "operator@example.test")
        monkeypatch.setenv("COPYLEAKS_API_KEY", "secret-key")

        def _fail(*_args, **_kwargs):
            raise ExternalScanError("provider timeout")

        monkeypatch.setattr("backend.plagiarism.service.external.fetch_external_report", _fail)

        started = session.post(
            f"/api/documents/{document_id}/plagiarism/scan",
            headers=headers,
            json={"provider": "external", "engines": ["lexical"], "consent_external": True},
        )
        assert started.status_code == 200, started.text
        scan = _wait_for_scan(session, headers, started.json()["scan_id"])
        assert scan["status"] == "failed"
        assert "provider timeout" in scan["error"]
        assert scan.get("report") is None


def test_external_provider_requires_consent_and_configuration(tmp_path, monkeypatch):
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])
        monkeypatch.setenv("PAPERPILOT_PLAGIARISM_PROVIDER", "copyleaks")
        monkeypatch.setenv("COPYLEAKS_EMAIL", "operator@example.test")
        monkeypatch.setenv("COPYLEAKS_API_KEY", "secret-key")

        no_consent = session.post(
            f"/api/documents/{document_id}/plagiarism/scan",
            headers=headers,
            json={"provider": "external", "consent_external": False},
        )
        assert no_consent.status_code == 400
        assert "consent" in no_consent.json()["detail"].lower()

    monkeypatch.delenv("COPYLEAKS_API_KEY", raising=False)
    with TestClient(app) as session:
        headers = _register(session)
        document_id = _upload_and_analyze(session, headers, tmp_path, [COPILED_SENTENCE])
        response = session.post(
            f"/api/documents/{document_id}/plagiarism/scan",
            headers=headers,
            json={"provider": "external", "consent_external": True},
        )
        assert response.status_code == 400


def test_plagiarism_status_never_exposes_credentials(monkeypatch):
    monkeypatch.setenv("PAPERPILOT_PLAGIARISM_PROVIDER", "copyleaks")
    monkeypatch.setenv("COPYLEAKS_EMAIL", "operator@example.test")
    monkeypatch.setenv("COPYLEAKS_API_KEY", "super-secret-key")
    with TestClient(app) as session:
        headers = _register(session)
        response = session.get("/api/plagiarism/status", headers=headers)
        assert response.status_code == 200
        body = response.text
        assert "super-secret-key" not in body
        assert "operator@example.test" not in body
        assert response.json()["external"]["configured"] is True
        assert response.json()["semantic"]["status"] in {"available", "unavailable"}
