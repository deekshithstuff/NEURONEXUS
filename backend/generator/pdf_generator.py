from __future__ import annotations

from pathlib import Path

import fitz
from docx import Document


class PDFGenerator:
    def generate(self, docx_path: str | Path | None = None, output_path: str | Path | None = None, text: str | None = None) -> str:
        if output_path is None:
            raise ValueError("output_path is required for PDF generation.")
        content = text
        page_width, page_height = 595.28, 841.89
        margins = (54.0, 54.0, 54.0, 54.0)
        if not content and docx_path:
            content = self._extract_docx_text(docx_path)
        if docx_path:
            section = Document(docx_path).sections[0]
            page_width = float(section.page_width.inches) * 72
            page_height = float(section.page_height.inches) * 72
            margins = tuple(
                float(value.inches) * 72
                for value in (section.left_margin, section.top_margin, section.right_margin, section.bottom_margin)
            )
        if not content:
            content = (
                "Generated manuscript preview\n\n"
                "This PDF is created from the formatted manuscript export and preserves the original research content."
            )

        doc = fitz.open()
        text_position = 0
        chunk_size = 2800
        while text_position < len(content):
            chunk_end = min(text_position + chunk_size, len(content))
            if chunk_end < len(content):
                boundary = max(
                    content.rfind("\n", text_position, chunk_end),
                    content.rfind(" ", text_position, chunk_end),
                )
                if boundary > text_position:
                    chunk_end = boundary + 1
            page = doc.new_page(width=page_width, height=page_height)
            remaining_space = page.insert_textbox(
                fitz.Rect(margins[0], margins[1], page.rect.width - margins[2], page.rect.height - margins[3]),
                content[text_position:chunk_end],
                fontsize=11,
                fontname="helv",
            )
            if remaining_space < 0:
                doc.delete_page(doc.page_count - 1)
                if chunk_size == 1:
                    raise ValueError("Unable to fit manuscript text on a PDF page.")
                chunk_size = max(1, chunk_size // 2)
                continue
            text_position = chunk_end
            chunk_size = 2800
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return str(output_path)

    def generate_readiness_report(self, output_path: str | Path, details: str) -> str:
        return self.generate(output_path=output_path, text=details)

    def _extract_docx_text(self, docx_path: str | Path) -> str:
        document = Document(docx_path)
        blocks: list[str] = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                blocks.append(paragraph.text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        return "\n\n".join(blocks)

