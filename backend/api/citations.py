from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.citation.validator import validate_citations
from backend.database import fetch_all, fetch_one

router = APIRouter(prefix="/api/citations")


class CheckRequest(BaseModel):
    citations: list[dict]
    references: list[dict]


@router.post("/check")
async def check_citations(body: CheckRequest):
    report = validate_citations(body.citations, body.references)
    return report


@router.get("/{document_id}")
async def get_citation_report(document_id: str):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document or not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document not found or not analyzed.")
    analysis = json.loads(document["analysis_json"])
    issues = validate_citations(analysis.get("citations", []), analysis.get("references", []))
    return {
        "document_id": document_id,
        "total_citations": len(analysis.get("citations", [])),
        "total_references": len(analysis.get("references", [])),
        **issues,
    }
