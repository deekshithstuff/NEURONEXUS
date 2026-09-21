from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse

from backend.config import OUTPUT_DIR
from backend.database import fetch_one
from backend.formatting.formatter import apply_formatting
from backend.generator.docx_generator import DOCXGenerator
from backend.generator.package_generator import SubmissionPackageGenerator
from backend.generator.pdf_generator import PDFGenerator
from backend.journal.rules import get_journal_rules

router = APIRouter(prefix="/api/documents")


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
    formatted = apply_formatting(analysis, journal_rules)
    return formatted.model_dump()


@router.post("/{document_id}/generate")
async def generate_document(document_id: str):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document or not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document not found or not analyzed.")
    analysis = json.loads(document["analysis_json"])
    journal_id = document["selected_journal_id"] or "nature"
    try:
        journal_rules = get_journal_rules(journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    output_dir = OUTPUT_DIR / document_id
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / "final_manuscript.docx"
    pdf_path = output_dir / "final_manuscript.pdf"
    readiness_pdf = output_dir / "readiness_report.pdf"

    DOCXGenerator().generate(analysis, docx_path)
    PDFGenerator().generate(docx_path, pdf_path)
    report_details = (
        f"Research publication readiness report\n\n"
        f"Document: {analysis.get('document_id', document_id)}\n"
        f"Title: {analysis.get('title', 'Untitled manuscript')}\n"
        f"Journal: {journal_rules.get('journal_name', journal_id)}\n"
        f"Sections: {len(analysis.get('sections', []))}\n"
        f"Figures: {len(analysis.get('figures', []))}\n"
        f"Tables: {len(analysis.get('tables', []))}\n"
        f"Citations: {len(analysis.get('citations', []))}\n"
        f"References: {len(analysis.get('references', []))}\n"
        "\nStatus: ready for formatting review and journal submission packaging."
    )
    PDFGenerator().generate_readiness_report(readiness_pdf, report_details)

    package_dir = output_dir / "submission_package"
    package = SubmissionPackageGenerator().build(
        document_id,
        package_dir,
        docx_path,
        pdf_path,
        readiness_pdf,
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
