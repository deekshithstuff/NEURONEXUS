from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


class SubmissionPackageGenerator:
    def build(
        self,
        document_id: str,
        output_dir: str | Path,
        manuscript_docx: str | Path,
        manuscript_pdf: str | Path,
        readiness_report_pdf: str | Path | None = None,
        journal_name: str | None = None,
    ) -> dict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        final_docx = output_dir / "final_manuscript.docx"
        final_pdf = output_dir / "final_manuscript.pdf"
        readiness_report = output_dir / "readiness_report.pdf"
        checklist = output_dir / "submission_checklist.txt"

        shutil.copy2(manuscript_docx, final_docx)
        shutil.copy2(manuscript_pdf, final_pdf)
        if readiness_report_pdf is not None:
            shutil.copy2(readiness_report_pdf, readiness_report)

        checklist.write_text(
            "\n".join(
                [
                    f"Submission package for {document_id}",
                    f"Target journal: {journal_name or 'unspecified'}",
                    "",
                    "Included files:",
                    "- final_manuscript.docx",
                    "- final_manuscript.pdf",
                    "- readiness_report.pdf",
                    "- figures/",
                    "",
                    "Before journal submission:",
                    "1. Review journal-specific captions and reference style.",
                    "2. Confirm author names, affiliations, and corresponding author email.",
                    "3. Verify that figures and tables are complete.",
                    "4. Address items listed in the readiness report.",
                ]
            ),
            encoding="utf-8",
        )

        zip_path = Path(output_dir).parent / "submission_package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in output_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, arcname=str(path.relative_to(output_dir)))

        return {
            "document_id": document_id,
            "package_dir": str(output_dir),
            "final_docx": str(final_docx),
            "final_pdf": str(final_pdf),
            "readiness_report": str(readiness_report),
            "figures_dir": str(figures_dir),
            "checklist": str(checklist),
            "zip_path": str(zip_path),
        }
