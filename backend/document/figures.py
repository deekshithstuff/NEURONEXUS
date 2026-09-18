from __future__ import annotations

from typing import Iterable

from docx import Document

from .models import Figure


def extract_figures(document: Document, section_name: str | None = None) -> list[Figure]:
    """Extract figure placeholders and captions from a DOCX document."""
    figures: list[Figure] = []
    for index, shape in enumerate(document.inline_shapes, start=1):
        caption = ""
        try:
            doc_pr = shape._inline.xpath(".//wp:docPr")
            if doc_pr:
                caption = doc_pr[0].get("descr") or ""
        except Exception:  # pragma: no cover - defensive parsing
            caption = ""
        figures.append(
            Figure(
                id=f"Figure {index}",
                caption=caption,
                section=section_name,
                position=index,
                image_name=f"figure_{index}.png",
            )
        )
    return figures


def validate_figure_preservation(figures: Iterable[Figure]) -> list[str]:
    warnings: list[str] = []
    for figure in figures:
        if not figure.caption and not figure.image_name:
            warnings.append(f"Figure {figure.id} is missing both caption and image metadata.")
    return warnings
