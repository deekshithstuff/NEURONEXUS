from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.citation.validator import validate_citations
from backend.database import fetch_all, fetch_one
from backend.journal.rules import get_journal_rules

router = APIRouter(prefix="/api/citations")


class CheckRequest(BaseModel):
    citations: list[dict]
    references: list[dict]
    citation_style: str | None = None


@router.post("/check")
async def check_citations(body: CheckRequest):
    report = validate_citations(body.citations, body.references, body.citation_style)
    return report


@router.get("/{document_id}")
async def get_citation_report(document_id: str):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document or not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document not found or not analyzed.")
    analysis = json.loads(document["analysis_json"])
    journal_id = document["selected_journal_id"] or "nature"
    journal = get_journal_rules(journal_id)
    issues = validate_citations(
        analysis.get("citations", []), analysis.get("references", []), journal.get("citation_style")
    )
    return {
        "document_id": document_id,
        "total_citations": len(analysis.get("citations", [])),
        "total_references": len(analysis.get("references", [])),
        **issues,
    }
