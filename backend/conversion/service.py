"""Multi-journal manuscript conversion orchestration.

Each selected journal produces an independent conversion job with its own
output directory, so formatting one journal never overwrites another. The
service reuses the existing formatting engine, DOCX/PDF generators, approved
change application, and the shared compliance engine.
"""

from __future__ import annotations

import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.ai_service import apply_approved_changes
from backend.compliance.engine import build_compliance_report, word_limit_analysis
from backend.config import OUTPUT_DIR
from backend.database import connection, fetch_all, fetch_one
from backend.formatting.formatter import apply_formatting
from backend.generator.apply_changes import apply_changes_to_source
from backend.generator.docx_generator import DOCXGenerator
from backend.generator.pdf_generator import PDFGenerator
from backend.journal.rules import get_journal_rules
from backend.security import get_accessible_document

CONVERSION_ROOT = OUTPUT_DIR / "conversions"
logger = logging.getLogger(__name__)


class ConversionError(ValueError):
    """Raised for invalid or unauthorized conversion requests."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_job(row) -> dict[str, Any]:
    result = json.loads(row["result_json"]) if row["result_json"] else None
    if result and isinstance(result.get("outputs"), dict):
        result["outputs"] = {
            name: bool(path)
            for name, path in result["outputs"].items()
        }
    return {
        "job_id": row["id"],
        "document_id": row["document_id"],
        "journal_id": row["journal_id"],
        "article_type": row["article_type"],
        "status": row["status"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "result": result,
    }


def start_conversion(
    document_id: str,
    user: dict,
    journal_ids: list[str],
    *,
    article_type: str | None = None,
    approved_changes: list[dict] | None = None,
) -> list[dict[str, Any]]:
    document, _ = get_accessible_document(document_id, user, capability="convert")
    if not document["analysis_json"]:
        raise ConversionError("Analyze the manuscript before converting it.")
    if not journal_ids:
        raise ConversionError("Select at least one journal to convert for.")
    normalized: list[str] = []
    for journal_id in journal_ids:
        key = str(journal_id).strip().lower()
        if key and key not in normalized:
            normalized.append(key)
    if not normalized:
        raise ConversionError("Select at least one journal to convert for.")
    # Validate every journal up-front so a bad id fails the whole request clearly.
    for key in normalized:
        try:
            get_journal_rules(key)
        except ValueError as exc:
            raise ConversionError(str(exc)) from exc

    jobs: list[dict[str, Any]] = []
    timestamp = _now()
    options = json.dumps({"approved_changes": approved_changes or []})
    with connection() as conn:
        for journal_id in normalized:
            job_id = f"CVJ-{uuid.uuid4().hex[:10].upper()}"
            conn.execute(
                "INSERT INTO conversion_jobs "
                "(id, document_id, user_id, journal_id, article_type, status, options_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, document_id, user["id"], journal_id, article_type, "queued", options, timestamp, timestamp),
            )
            jobs.append(
                {
                    "job_id": job_id,
                    "document_id": document_id,
                    "journal_id": journal_id,
                    "article_type": article_type,
                    "status": "queued",
                }
            )
    return jobs


def run_conversion(job_id: str) -> None:
    row = fetch_one("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,))
    if row is None:
        return
    _update_job(job_id, status="running")
    try:
        document_id = row["document_id"]
        journal_id = row["journal_id"]
        document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
        if document is None or not document["analysis_json"]:
            raise ConversionError("The manuscript is no longer available for conversion.")
        analysis = json.loads(document["analysis_json"])
        journal = get_journal_rules(journal_id)
        options = json.loads(row["options_json"]) if row["options_json"] else {}
        approved_changes = options.get("approved_changes") or []
        applied_changes: list[dict] = []
        skipped_changes: list[dict] = []
        if approved_changes:
            analysis, applied_changes, skipped_changes = apply_approved_changes(analysis, approved_changes)

        result = _convert_one(
            job_id,
            document_id,
            analysis,
            document,
            journal,
            row["article_type"],
            applied_changes=applied_changes,
            skipped_changes=skipped_changes,
        )
        _update_job(job_id, status="completed", result=result)
    except ConversionError as exc:
        _update_job(job_id, status="failed", error=str(exc) or "The conversion failed.")
    except ValueError:
        logger.exception("Conversion job %s failed validation", job_id)
        _update_job(job_id, status="failed", error="The conversion could not process this manuscript.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Conversion job %s failed", job_id)
        _update_job(job_id, status="failed", error="Conversion failed unexpectedly; retry or review the source document.")


def _convert_one(
    job_id: str,
    document_id: str,
    analysis: dict,
    document,
    journal: dict,
    article_type: str | None,
    *,
    applied_changes: list[dict] | None = None,
    skipped_changes: list[dict] | None = None,
) -> dict[str, Any]:
    journal_id = journal["journal_id"]
    output_dir = CONVERSION_ROOT / document_id / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / "manuscript.docx"
    pdf_path = output_dir / "manuscript.pdf"
    compliance_json = output_dir / "compliance_report.json"
    compliance_pdf = output_dir / "compliance_report.pdf"

    formatting_result = apply_formatting(analysis, journal)
    source_path = Path(document["original_path"]) if document["original_path"] else None
    source_is_pdf = bool(source_path and source_path.suffix.lower() == ".pdf")
    source_for_generation = None if source_is_pdf else source_path
    if not source_is_pdf and source_path and applied_changes:
        source_for_generation = apply_changes_to_source(
            source_path, output_dir / "source_accepted.docx", applied_changes
        )

    warnings = list(formatting_result.warnings)
    if source_is_pdf:
        warnings.append(
            "The source was a PDF; the DOCX export was reconstructed from extracted text and may not preserve the original layout, figures, or tables."
        )

    DOCXGenerator().generate(analysis, docx_path, journal, source_path=source_for_generation)
    if not docx_path.is_file() or docx_path.stat().st_size == 0:
        raise ConversionError("DOCX generation did not produce an output file.")
    with zipfile.ZipFile(docx_path) as archive:
        if archive.testzip() is not None:
            raise ConversionError("Generated DOCX failed archive validation.")
    pdf_rendering = {
        "status": "limited_text_rendering",
        "message": "PDF text is extracted from the formatted DOCX; office layout and visual fidelity are not guaranteed because no office renderer is configured.",
    }
    try:
        PDFGenerator().generate(docx_path, pdf_path)
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise ConversionError("PDF generation produced no output.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("PDF rendering failed for conversion job %s", job_id)
        pdf_path.unlink(missing_ok=True)
        pdf_rendering = {"status": "failed", "message": "PDF rendering failed; the DOCX and compliance report remain available."}
        warnings.append(pdf_rendering["message"])

    page_count = (analysis.get("metadata") or {}).get("page_count")
    compliance = build_compliance_report(
        analysis,
        journal,
        article_type=article_type,
        source_format=(analysis.get("metadata") or {}).get("source_format"),
        page_count=page_count,
    )
    limits = word_limit_analysis(analysis, journal)
    compliance_json.write_text(json.dumps(compliance, indent=2), encoding="utf-8")

    report_lines = [
        "Journal compliance report",
        f"Manuscript: {analysis.get('title') or document_id}",
        f"Target journal: {journal.get('journal_name')}",
        f"Article type: {compliance['article_type']}",
        f"Guide verification: {compliance['guide_verification_status']}",
        f"Overall status: {compliance['overall_status']}",
        f"Automated compliance score: {compliance['compliance_score']}",
        "",
        "Rules:",
    ]
    for rule in compliance["rules"]:
        report_lines.append(f"- [{rule['status']}] {rule['description']} ({rule['actual']})")
    report_lines.append("")
    report_lines.append("This is a rule-based check; rules marked manual_review require human verification.")
    try:
        PDFGenerator().generate_readiness_report(compliance_pdf, "\n".join(report_lines))
        if not compliance_pdf.is_file() or compliance_pdf.stat().st_size == 0:
            raise ConversionError("Compliance PDF generation produced no output.")
    except Exception:  # pragma: no cover - defensive
        logger.exception("Compliance PDF generation failed for conversion job %s", job_id)
        compliance_pdf.unlink(missing_ok=True)
        warnings.append("Compliance PDF could not be rendered; the JSON compliance report remains available.")

    outputs = {
        "docx": str(docx_path),
        "pdf": str(pdf_path) if pdf_path.exists() else None,
        "compliance_json": str(compliance_json),
        "compliance_pdf": str(compliance_pdf) if compliance_pdf.exists() else None,
    }
    with connection() as conn:
        for file_format, file_path in outputs.items():
            if file_path:
                conn.execute(
                    "INSERT OR REPLACE INTO conversion_outputs(id, job_id, document_id, journal_id, format, path) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (f"{job_id}-{file_format}", job_id, document_id, journal_id, file_format, file_path),
                )
    return {
        "document_id": document_id,
        "journal_id": journal_id,
        "journal_name": journal.get("journal_name"),
        "template_name": journal.get("template_name"),
        "article_type": compliance["article_type"],
        "guideline": journal.get("guideline"),
        "outputs": outputs,
        "applied_rules": formatting_result.applied_rules,
        "warnings": warnings,
        "compliance_summary": {
            "overall_status": compliance["overall_status"],
            "compliance_score": compliance["compliance_score"],
            "counts": compliance["counts"],
            "failed_rules": compliance["failed_rules"],
            "manual_review_required": compliance["manual_review_required"],
        },
        "compliance_report": compliance,
        "word_limit": limits,
        "changes_summary": [
            "Applied configured page size and margins.",
            "Applied configured body font, size, and spacing where supported.",
            "Preserved equations, tables, images, captions, citations, and references from the source.",
            "In-text citation and bibliography style conversion is not applied; entries are preserved as authored.",
        ],
        "approved_changes": {
            "applied": applied_changes or [],
            "skipped": skipped_changes or [],
        },
        "pdf_rendering": pdf_rendering,
    }


def get_job(job_id: str, user: dict) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise ConversionError("Conversion job not found.")
    get_accessible_document(row["document_id"], user, capability="read")
    return _public_job(row)


def list_jobs(document_id: str, user: dict) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="read")
    rows = fetch_all(
        "SELECT * FROM conversion_jobs WHERE document_id = ? ORDER BY created_at DESC, id",
        (document_id,),
    )
    return {"document_id": document_id, "jobs": [_public_job(row) for row in rows]}


def retry_job(job_id: str, user: dict) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise ConversionError("Conversion job not found.")
    get_accessible_document(row["document_id"], user, capability="convert")
    if row["status"] != "failed":
        raise ConversionError("Only failed conversion jobs can be retried.")
    with connection() as conn:
        conn.execute("DELETE FROM conversion_outputs WHERE job_id = ?", (job_id,))
        conn.execute(
            "UPDATE conversion_jobs SET status = 'queued', error = NULL, result_json = NULL, "
            "updated_at = ? WHERE id = ? AND status = 'failed'",
            (_now(), job_id),
        )
    retried = fetch_one("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,))
    return _public_job(retried)


def job_output_path(job_id: str, user: dict, file_format: str) -> tuple[str, Path, str]:
    row = fetch_one("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise ConversionError("Conversion job not found.")
    get_accessible_document(row["document_id"], user, capability="read")
    if row["status"] != "completed" or not row["result_json"]:
        raise ConversionError("The conversion output is not ready yet.")
    output = fetch_one(
        "SELECT path FROM conversion_outputs WHERE job_id = ? AND format = ?",
        (job_id, file_format),
    )
    if output is None:
        raise ConversionError("That output is not available for this conversion.")
    target = Path(output["path"])
    if not target.exists():
        raise ConversionError("The conversion output file is missing.")
    media = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "compliance_json": "application/json",
        "compliance_pdf": "application/pdf",
    }.get(file_format, "application/octet-stream")
    extension = target.suffix.lstrip(".") or "bin"
    filename = f"{row['journal_id']}_{file_format}.{extension}"
    return filename, target, media


def _update_job(job_id: str, *, status: str, result: dict | None = None, error: str | None = None) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE conversion_jobs SET status = ?, result_json = COALESCE(?, result_json), "
            "error = ?, updated_at = ? WHERE id = ?",
            (status, json.dumps(result) if result is not None else None, error, _now(), job_id),
        )
