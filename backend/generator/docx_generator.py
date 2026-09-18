from __future__ import annotations

from pathlib import Path

from docx import Document


class DOCXGenerator:
    def generate(self, document: dict, output_path: str | Path) -> str:
        doc = Document()
        doc.add_heading(document.get("title") or "Untitled manuscript", level=1)
        for section in document.get("sections", []):
            if section.get("heading"):
                doc.add_heading(section["heading"], level=min(section.get("level", 1), 4))
            if section.get("content"):
                doc.add_paragraph(section["content"])
        doc.save(output_path)
        return str(output_path)
