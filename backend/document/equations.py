from __future__ import annotations

from lxml import etree

from docx import Document

from .models import Equation


def extract_equations(document: Document, section_name: str | None = None) -> list[Equation]:
    """Preserve OMML equation XML when present in the DOCX body."""
    equations: list[Equation] = []
    namespace = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}

    for index, element in enumerate(document.element.body.iter(), start=1):
        if element.tag == etree.QName(namespace["m"], "oMath") or element.tag == etree.QName(namespace["m"], "oMathPara"):
            equations.append(
                Equation(
                    id=f"Equation {len(equations) + 1}",
                    position=index,
                    xml=etree.tostring(element, encoding="unicode"),
                    section=section_name,
                )
            )
    return equations
