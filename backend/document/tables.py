from __future__ import annotations

from docx import Document

from .models import TableData


def extract_tables(document: Document, section_name: str | None = None) -> list[TableData]:
    """Extract tables and their cell content while preserving order."""
    tables: list[TableData] = []
    for index, table in enumerate(document.tables, start=1):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        tables.append(
            TableData(
                id=f"Table {index}",
                caption="",
                section=section_name,
                position=index,
                content=rows,
            )
        )
    return tables
