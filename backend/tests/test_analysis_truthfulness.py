from uuid import uuid4

from backend.ai_service import analyze_completeness, analyze_contribution, analyze_methodology, analyze_novelty, analyze_writing, generate_improvements, generate_journal_match, generate_readiness_report
from backend.citation.validator import validate_citations
from backend.ai_provider import LocalMockProvider, ai_provider_status, get_ai_provider
from backend.main import app
from backend.journal.database import load_journal_rules
from fastapi.testclient import TestClient

client = TestClient(app)
account = client.post(
    "/api/auth/register",
    json={"name": "Analysis test", "email": f"analysis-{uuid4()}@example.test", "password": "correct-horse-battery"},
)
assert account.status_code == 200, account.text
client.headers.update({"Authorization": f"Bearer {account.json()['access_token']}"})


def test_novelty_does_not_invent_external_comparisons():
    result = analyze_novelty("DOC-EMPTY", {"title": "A study"})

    assert "similar_papers" not in result
    assert result["originality_score"] is None
    assert result["originality_status"] == "not_configured"
    assert "no external scholarly search" in result["analysis_scope"]
    assert result["novelty_score"] < 100


def test_readiness_scores_respond_to_evidence_and_are_transparent():
    sparse = {"title": "A study", "sections": [], "paragraphs": [], "keywords": []}
    evidence_rich = {
        "title": "A reproducible method for measured outcomes",
        "abstract": "We propose a method to address a research gap and compare it with prior work.",
        "keywords": ["method", "evaluation", "reproducibility"],
        "paragraphs": ["The contribution is evaluated against a baseline with measurable results."],
        "sections": [
            {"type": "abstract", "heading": "Abstract", "content": "We propose a method."},
            {"type": "introduction", "heading": "Introduction", "content": "The research gap is limited prior work."},
            {"type": "methodology", "heading": "Methodology", "content": "We use a dataset of 1200 samples, preprocessing, training parameters, baseline comparison, and F1 metrics."},
            {"type": "results", "heading": "Results", "content": "The method improves F1 by 12% over the baseline."},
            {"type": "conclusion", "heading": "Conclusion", "content": "Limitations include the single dataset."},
            {"type": "references", "heading": "References", "content": "References"},
        ],
        "citations": [],
        "references": [],
    }

    sparse_report = generate_readiness_report("DOC-SPARSE", sparse, selected_journal="nature")
    evidence_report = generate_readiness_report("DOC-EVIDENCE", evidence_rich, selected_journal="nature")

    assert sparse_report["overall_readiness"] != evidence_report["overall_readiness"]
    assert evidence_report["scores"]["methodology"] > sparse_report["scores"]["methodology"]
    assert evidence_report["scores"]["novelty_framing"] > sparse_report["scores"]["novelty_framing"]
    assert evidence_report["overall_readiness"] == round(sum(evidence_report["scores"].values()) / len(evidence_report["scores"]))
    assert evidence_report["recommendations"]
    assert "not configured" in evidence_report["novelty_scope"]


def test_dashboard_summary_counts_stored_documents():
    response = client.get("/api/documents/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["manuscript_count"] == len(client.get("/api/documents").json()["documents"])
    assert body["analyzed_count"] <= body["manuscript_count"]
    assert body["readiness_average"] is None or 0 <= body["readiness_average"] <= 100
    assert "methodology" in body["dimension_averages"] or body["analyzed_count"] == 0


def test_methodology_and_contribution_scores_require_document_evidence():
    empty_method = analyze_methodology("DOC-EMPTY", {"sections": [], "paragraphs": []})
    evidence_method = analyze_methodology("DOC-EVIDENCE", {
        "sections": [{"type": "methodology", "heading": "Methodology", "content": "We trained a model on a dataset of 2,000 samples and report F1 metrics against a baseline."}],
    })
    empty_contribution = analyze_contribution("DOC-EMPTY", {"sections": [], "paragraphs": []})

    assert empty_method["score"] == 0
    assert evidence_method["score"] > empty_method["score"]
    assert evidence_method["detected_information"]
    assert empty_contribution["technical_contribution_score"] == 0
    assert empty_contribution["missing_evidence"]


def test_writing_and_improvement_findings_use_actual_text():
    source_sentence = "This is obviously a very long sentence " + "with several clauses " * 10 + "."
    analysis = {
        "sections": [{"type": "introduction", "heading": "Introduction", "content": source_sentence}],
        "paragraphs": [source_sentence],
        "keywords": [],
    }

    writing = analyze_writing("DOC-WRITING", analysis)
    improvements = generate_improvements("DOC-WRITING", analysis)

    assert writing["sentence_findings"]
    assert all(finding["original"] == source_sentence for finding in writing["sentence_findings"])
    assert improvements["source_modified"] is False
    assert all(item["original"] == source_sentence or item["original"].startswith("No source sentence") for item in improvements["suggestions"])


def test_journal_profiles_resolve_complete_generic_rule_schema():
    profiles = load_journal_rules()
    by_id = {profile["journal_id"]: profile for profile in profiles}
    expected = {
        "nature", "ieee", "ieee_transactions", "ieee_access", "ieee_conference",
        "acm_journal", "acm_conference", "springer_nature", "springer_lncs",
        "elsevier_generic", "elsevier_two_column", "wiley_generic", "mdpi_generic", "taylor_francis_generic",
    }
    required_fields = {
        "publisher", "template_id", "article_type", "page_size", "orientation", "margins", "layout",
        "font", "font_size", "line_spacing", "paragraph_spacing", "heading_styles", "heading_numbering",
        "title_formatting", "author_formatting", "affiliation_formatting", "abstract_formatting",
        "keyword_formatting", "section_order", "figure_rules", "table_rules", "equation_rules",
        "page_numbering", "header_footer_rules", "citation_style", "reference_style", "bibliography_formatting",
        "word_limit", "page_limit", "required_sections", "optional_sections", "supplementary_material_rules",
        "manuscript_structure", "article_specific_restrictions", "profile_basis",
    }

    assert expected <= by_id.keys()
    assert all(required_fields <= profile.keys() for profile in profiles)
    assert all("not verified" in profile["profile_basis"].lower() for profile in profiles)


def test_citation_validator_reports_numbering_style_and_reference_quality_issues():
    citations = [
        {"text": "[1, 1]", "citation_type": "numeric", "reference_ids": ["1", "1"]},
        {"text": "[3]", "citation_type": "numeric", "reference_ids": ["3"]},
    ]
    references = [
        {"id": "1", "raw_text": "1. Lee, A. A complete article title. Journal of Testing. 2024."},
        {"id": "3", "raw_text": "3. X", "title": "X"},
    ]

    report = validate_citations(citations, references, "author-year")

    assert report["duplicate_citation_numbers"]
    assert any(issue["type"] == "missing_reference_number" for issue in report["numbering_issues"])
    assert report["style_mismatches"]
    assert report["malformed_references"]
    assert report["missing_dois"]
    assert citations[0]["reference_ids"] == ["1", "1"]


def test_ai_provider_uses_local_rules_without_configured_credentials(monkeypatch):
    monkeypatch.delenv("PAPERPILOT_AI_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    provider = get_ai_provider()
    status = ai_provider_status()

    assert isinstance(provider, LocalMockProvider)
    assert status["configured"] is False
    assert status["status"] == "limited_analysis"


def test_reference_checks_use_raw_text_from_docx_parser():
    references = [
        {"id": "1", "raw_text": "[1] Smith J. et al. Clinical benchmarking. Journal of Methods. 2024.", "year": "2024"},
        {"id": "2", "raw_text": "[2] Smith J. et al. Clinical benchmarking. Journal of Methods. 2024.", "year": "2024"},
    ]
    citations = [{"text": "Smith et al. (2024)", "citation_type": "author_year", "reference_ids": []}]

    report = validate_citations(citations, references)

    assert report["duplicate_references"]
    assert report["uncited_references"] == []


def test_unrelated_manuscript_does_not_receive_a_positive_journal_match():
    result = generate_journal_match("DOC-UNRELATED", {
        "title": "Quasar remnant circulation under distant stellar tides",
        "abstract": "This paper describes observations of a quasar remnant.",
        "keywords": ["quasar", "stellar tides"],
    }, "nature")

    assert result["score"] == 0
    assert result["relevant_topics"] == []
    assert result["formatting_compatibility"] < 100


def test_completeness_reports_configured_word_limits():
    from backend.journal.rules import get_journal_rules

    journal = get_journal_rules("nature")
    abstract_limit = journal["abstract_formatting"]["max_words"]
    analysis = {
        "title": "Test title",
        "abstract": " ".join(["abstract"] * (abstract_limit + 1)),
        "sections": [{"type": "introduction", "content": " ".join(["manuscript"] * (journal["word_limit"] + 1))}],
        "keywords": [],
        "figures": [],
        "tables": [],
        "equations": [],
    }

    result = analyze_completeness("DOC-LIMITS", analysis, "nature")

    assert result["word_count"] > result["word_limit"]
    assert result["word_limit_exceeded"] is True
    assert result["abstract_word_count"] == abstract_limit + 1
    assert result["abstract_limit_exceeded"] is True
from uuid import uuid4
