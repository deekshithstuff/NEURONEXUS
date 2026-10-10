from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from docx import Document
from starlette.responses import FileResponse

from backend.ai_service import apply_approved_changes, generate_readiness_report
from backend.config import OUTPUT_DIR
from backend.database import connection
from backend.formatting.formatter import apply_formatting
from backend.generator.docx_generator import DOCXGenerator
from backend.generator.package_generator import SubmissionPackageGenerator
from backend.generator.pdf_generator import PDFGenerator
from backend.journal.rules import get_journal_rules
from backend.security import get_current_user, get_owned_document

router = APIRouter(prefix="/api/documents", dependencies=[Depends(get_current_user)])


def _persist_journal(document_id: str, journal_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE documents SET selected_journal_id = ?, status = ? WHERE id = ?",
            (journal_id, "formatted", document_id),
        )


def _apply_approved_changes_to_source(source_path: Path, output_path: Path, applied_changes: list[dict]) -> Path:
    """Rewrite a DOCX source in place so accepted improvements land in the final document."""
    doc = Document(source_path)
    for change in applied_changes:
        original = change.get("original") or ""
        suggested = change.get("suggested") or ""
        if not original or not suggested:
            continue
        pattern = re.compile(
            r"\s+".join(re.escape(part) for part in original.split() if part),
            flags=re.IGNORECASE,
        )
        for paragraph in doc.paragraphs:
            match = pattern.search(paragraph.text)
            if not match:
                continue
            for run in paragraph.runs:
                if run.text and run.text.strip() and pattern.search(run.text):
                    run.text = pattern.sub(suggested, run.text, count=1)
                    match = None
                    break
            if match is not None:
                start, end = match.span()
                paragraph.runs[0].text = paragraph.text[:start] + suggested + paragraph.text[end:]
                for extra_run in paragraph.runs[1:]:
                    extra_run.text = ""
    doc.save(output_path)
    return output_path


@router.post("/{document_id}/format")
async def format_document(
    document_id: str,
    payload: dict | None = None,
    user: dict = Depends(get_current_user),
):
    document = get_owned_document(document_id, user["id"])
    if not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document not found or not analyzed.")
    analysis = json.loads(document["analysis_json"])
    payload = payload or {}
    journal_id = payload.get("journal_id") or document["selected_journal_id"] or "nature"
    try:
        journal_rules = get_journal_rules(journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _persist_journal(document_id, journal_id)
    formatted = apply_formatting(analysis, journal_rules)
    if Path(document["original_path"]).suffix.lower() == ".pdf":
        formatted.warnings.append(
            "The source is a PDF; export reconstruction may not preserve the original layout, figures, or tables."
        )
    return formatted.model_dump()


@router.post("/{document_id}/generate")
async def generate_document(
    document_id: str,
    payload: dict | None = None,
    user: dict = Depends(get_current_user),
):
    document = get_owned_document(document_id, user["id"])
    if not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document not found or not analyzed.")
    analysis = json.loads(document["analysis_json"])
    payload = payload or {}
    journal_id = payload.get("journal_id") or document["selected_journal_id"] or "nature"
    try:
        journal_rules = get_journal_rules(journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _persist_journal(document_id, journal_id)
    output_dir = OUTPUT_DIR / document_id
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / "final_manuscript.docx"
    pdf_path = output_dir / "final_manuscript.pdf"
    readiness_pdf = output_dir / "readiness_report.pdf"

    approved_changes = payload.get("approved_changes") or []
    applied_changes, skipped_changes = [], []
    if approved_changes:
        analysis, applied_changes, skipped_changes = apply_approved_changes(analysis, approved_changes)
    formatting_result = apply_formatting(analysis, journal_rules)
    source_path = Path(document["original_path"])
    source_is_pdf = source_path.suffix.lower() == ".pdf"
    source_for_generation = None if source_is_pdf else source_path
    if not source_is_pdf and applied_changes:
        source_for_generation = _apply_approved_changes_to_source(
            source_path, output_dir / "source_accepted.docx", applied_changes
        )
    DOCXGenerator().generate(
        analysis,
        docx_path,
        journal_rules,
        source_path=source_for_generation,
    )
    if source_is_pdf:
        formatting_result.warnings.append(
            "The source was a PDF; the DOCX export was reconstructed from extracted text and may not preserve the original layout, figures, or tables."
        )
    PDFGenerator().generate(docx_path, pdf_path)
    readiness = generate_readiness_report(document_id, analysis, selected_journal=journal_id)
    score_lines = [f"- {name.replace('_', ' ').title()}: {score}/100" for name, score in readiness["scores"].items()]
    issue_lines = [
        f"- {issue['message']}"
        for issues in readiness["citation_issues"].values()
        for issue in issues
    ] or ["- No citation/reference consistency issues detected by the configured checks."]
    recommendation_lines = [
        f"- [{item['category']}] {item['issue']} Action: {item['suggested_action']}"
        for item in readiness["recommendations"]
    ] or ["- No prioritized recommendations were generated by the configured checks."]
    warning_lines = [f"- {warning}" for warning in formatting_result.warnings] or ["- No formatter warnings were reported."]
    report_details = "\n".join([
        "Research publication readiness report",
        f"Document: {analysis.get('document_id', document_id)}",
        f"Title: {analysis.get('title', 'Untitled manuscript')}",
        f"Journal profile: {journal_rules.get('journal_name', journal_id)}",
        f"Profile basis: {journal_rules.get('profile_basis', 'Not specified')}",
        f"\nOverall readiness: {readiness['overall_readiness']}/100",
        "\nDimension scores:",
        *score_lines,
        "\nCitation and reference findings:",
        *issue_lines,
        "\nPrioritized recommendations:",
        *recommendation_lines,
        "\nFormatting warnings:",
        *warning_lines,
        "\nThis rule-based assessment does not predict acceptance or verify global originality.",
    ])
    PDFGenerator().generate_readiness_report(readiness_pdf, report_details)

    package_dir = output_dir / "submission_package"
    package = SubmissionPackageGenerator().build(
        document_id,
        package_dir,
        docx_path,
        pdf_path,
        readiness_pdf,
        journal_name=journal_rules.get("journal_name"),
    )
    with connection() as conn:
        for file_format, file_path in [
            ("docx", docx_path),
            ("pdf", pdf_path),
            ("readiness_report", readiness_pdf),
            ("zip", package["zip_path"]),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO generated_documents(id, document_id, format, path) VALUES (?, ?, ?, ?)",
                (f"{document_id}-{file_format}", document_id, file_format, str(file_path)),
            )
    return {
        "document_id": document_id,
        "journal_id": journal_id,
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
        "submission_package": package,
        "readiness": readiness,
        "formatting_warnings": formatting_result.warnings,
        "approved_changes": {
            "applied": applied_changes,
            "skipped": skipped_changes,
        },
        "pdf_rendering": {
            "status": "limited_text_rendering",
            "message": "PDF text is extracted from the formatted DOCX; office layout and visual fidelity are not guaranteed because no office renderer is configured.",
        },
        "status": "generated",
    }


@router.get("/{document_id}/download/docx")
async def download_docx(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    target = OUTPUT_DIR / document_id / "final_manuscript.docx"
    if not target.exists():
        raise HTTPException(status_code=404, detail="DOCX output not yet generated.")
    return FileResponse(target, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename="final_manuscript.docx")


@router.get("/{document_id}/download/pdf")
async def download_pdf(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    target = OUTPUT_DIR / document_id / "final_manuscript.pdf"
    if not target.exists():
        raise HTTPException(status_code=404, detail="PDF output not yet generated.")
    return FileResponse(target, media_type="application/pdf", filename="final_manuscript.pdf")


@router.get("/{document_id}/download/report")
async def download_report(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    target = OUTPUT_DIR / document_id / "readiness_report.pdf"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Readiness report not yet generated.")
    return FileResponse(target, media_type="application/pdf", filename="readiness_report.pdf")


@router.get("/{document_id}/download/zip")
async def download_zip(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    target = OUTPUT_DIR / document_id / "submission_package.zip"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Submission package not yet generated.")
    return FileResponse(target, media_type="application/zip", filename="submission_package.zip")
