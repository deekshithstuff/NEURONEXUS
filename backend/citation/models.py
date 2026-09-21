from __future__ import annotations

from pydantic import BaseModel, Field


class CitationRecord(BaseModel):
    text: str
    citation_type: str
    location: str
    position: int
    reference_ids: list[str] = Field(default_factory=list)


class ReferenceRecord(BaseModel):
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
