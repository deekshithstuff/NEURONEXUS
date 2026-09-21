from __future__ import annotations

import shutil
from pathlib import Path


class SubmissionPackageGenerator:
    def build(
        self,
        document_id: str,
        output_dir: str | Path,
        manuscript_docx: str | Path,
        manuscript_pdf: str | Path,
        readiness_report_pdf: str | Path | None = None,
    ) -> dict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        final_docx = output_dir / "final_manuscript.docx"
        final_pdf = output_dir / "final_manuscript.pdf"
        readiness_report = output_dir / "readiness_report.pdf"

        shutil.copy2(manuscript_docx, final_docx)
        shutil.copy2(manuscript_pdf, final_pdf)
        if readiness_report_pdf is not None:
            shutil.copy2(readiness_report_pdf, readiness_report)

        return {
            "document_id": document_id,
            "package_dir": str(output_dir),
            "final_docx": str(final_docx),
            "final_pdf": str(final_pdf),
            "readiness_report": str(readiness_report),
            "figures_dir": str(figures_dir),
        }
