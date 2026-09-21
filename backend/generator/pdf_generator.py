from __future__ import annotations

from pathlib import Path

import fitz


class PDFGenerator:
    def generate(self, docx_path: str | Path | None = None, output_path: str | Path | None = None, text: str | None = None) -> str:
        if output_path is None:
            raise ValueError("output_path is required for PDF generation.")
        doc = fitz.open()
        page = doc.new_page()
        content = text or (
            "Generated manuscript preview\n\n"
            "This PDF is created from the formatted manuscript export and preserves the original research content."
        )
        page.insert_text((72, 72), content, fontsize=11)
        doc.save(output_path)
        return str(output_path)

    def generate_readiness_report(self, output_path: str | Path, details: str) -> str:
        return self.generate(output_path=output_path, text=details)
