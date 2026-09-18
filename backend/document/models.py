from typing import Any
from pydantic import BaseModel, Field

class Section(BaseModel):
    section_id: str
    heading: str
    type: str = "other"
    level: int = 1
    content: str = ""
    position: int

class Figure(BaseModel):
    id: str
    caption: str = ""
    section: str | None = None
    position: int
    image_name: str | None = None

class TableData(BaseModel):
    id: str
    caption: str = ""
    section: str | None = None
    position: int
    content: list[list[str]] = Field(default_factory=list)

class Equation(BaseModel):
    id: str
    position: int
    xml: str
    section: str | None = None

class Citation(BaseModel):
    text: str
    citation_type: str
    location: str
    position: int
    reference_ids: list[str] = Field(default_factory=list)

class Reference(BaseModel):
    id: str
    raw_text: str
    authors: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None

class DocumentAnalysis(BaseModel):
    document_id: str
    title: str = "Untitled manuscript"
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    figures: list[Figure] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    equations: list[Equation] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

class CitationIssue(BaseModel):
    type: str
    severity: str
    citation: str | None = None
    message: str

class CitationReport(BaseModel):
    document_id: str
    total_citations: int
    total_references: int
    missing_references: list[CitationIssue] = Field(default_factory=list)
    uncited_references: list[CitationIssue] = Field(default_factory=list)
    duplicate_references: list[CitationIssue] = Field(default_factory=list)
    numbering_issues: list[CitationIssue] = Field(default_factory=list)

class JournalRule(BaseModel):
    journal_id: str
    journal_name: str
    template_name: str
    page_size: str = "A4"
    margins: dict[str, float] = Field(default_factory=lambda: {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0})
    columns: int = 1
    font: str = "Times New Roman"
    font_size: float = 12
    line_spacing: float = 1.15
    paragraph_spacing: float = 6
    citation_style: str = "numeric"
    reference_style: str = "numbered"
    word_limit: int | None = None
    figure_rules: dict[str, Any] = Field(default_factory=dict)
    table_rules: dict[str, Any] = Field(default_factory=dict)
    heading_styles: dict[str, Any] = Field(default_factory=dict)

class FormatRequest(BaseModel):
    journal_id: str

class GenerateRequest(BaseModel):
    journal_id: str | None = None
    approved_changes: list[dict[str, Any]] = Field(default_factory=list)
    readiness_report: dict[str, Any] | None = None
