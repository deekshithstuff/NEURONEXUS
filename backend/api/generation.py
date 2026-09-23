from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse

from backend.config import OUTPUT_DIR
from backend.database import connection, fetch_one
from backend.formatting.formatter import apply_formatting
from backend.generator.docx_generator import DOCXGenerator
from backend.generator.package_generator import SubmissionPackageGenerator
from backend.generator.pdf_generator import PDFGenerator
from backend.journal.rules import get_journal_rules

router = APIRouter(prefix="/api/documents")


def _persist_journal(document_id: str, journal_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE documents SET selected_journal_id = ?, status = ? WHERE id = ?",
            (journal_id, "formatted", document_id),
        )


@router.post("/{document_id}/format")
async def format_document(document_id: str, payload: dict | None = None):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document or not document["analysis_json"]:
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
    return formatted.model_dump()


@router.post("/{document_id}/generate")
async def generate_document(document_id: str, payload: dict | None = None):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document or not document["analysis_json"]:
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

    apply_formatting(analysis, journal_rules)
    DOCXGenerator().generate(analysis, docx_path, journal_rules)
    PDFGenerator().generate(docx_path, pdf_path)
    report_details = (
        f"Research publication readiness report\n\n"
        f"Document: {analysis.get('document_id', document_id)}\n"
        f"Title: {analysis.get('title', 'Untitled manuscript')}\n"
        f"Journal: {journal_rules.get('journal_name', journal_id)}\n"
        f"Template: {journal_rules.get('template_name', journal_id)}\n"
        f"Font: {journal_rules.get('font')} {journal_rules.get('font_size')}pt\n"
        f"Page: {journal_rules.get('page_size')} / {journal_rules.get('columns')} column(s)\n"
        f"Citation style: {journal_rules.get('citation_style')}\n"
        f"Sections: {len(analysis.get('sections', []))}\n"
        f"Figures: {len(analysis.get('figures', []))}\n"
        f"Tables: {len(analysis.get('tables', []))}\n"
        f"Citations: {len(analysis.get('citations', []))}\n"
        f"References: {len(analysis.get('references', []))}\n"
        "\nStatus: formatted manuscript and readiness report packaged for submission review."
    )
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
    return {
        "document_id": document_id,
        "journal_id": journal_id,
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
        "submission_package": package,
        "status": "generated",
    }


@router.get("/{document_id}/download/docx")
async def download_docx(document_id: str):
    target = OUTPUT_DIR / document_id / "final_manuscript.docx"
    if not target.exists():
        raise HTTPException(status_code=404, detail="DOCX output not yet generated.")
    return FileResponse(target, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename="final_manuscript.docx")


@router.get("/{document_id}/download/pdf")
async def download_pdf(document_id: str):
    target = OUTPUT_DIR / document_id / "final_manuscript.pdf"
    if not target.exists():
        raise HTTPException(status_code=404, detail="PDF output not yet generated.")
    return FileResponse(target, media_type="application/pdf", filename="final_manuscript.pdf")


@router.get("/{document_id}/download/report")
async def download_report(document_id: str):
    target = OUTPUT_DIR / document_id / "readiness_report.pdf"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Readiness report not yet generated.")
    return FileResponse(target, media_type="application/pdf", filename="readiness_report.pdf")


@router.get("/{document_id}/download/zip")
async def download_zip(document_id: str):
    target = OUTPUT_DIR / document_id / "submission_package.zip"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Submission package not yet generated.")
    return FileResponse(target, media_type="application/zip", filename="submission_package.zip")
