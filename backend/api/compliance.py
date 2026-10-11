from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.compliance.engine import build_compliance_report, word_limit_analysis
from backend.compliance.requirements import available_article_types
from backend.database import fetch_one
from backend.journal.rules import get_journal_rules
from backend.security import get_current_user, get_accessible_document, require_capability

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


@router.get("/compliance/article-types")
async def list_article_types():
    return {"article_types": available_article_types()}


def _compliance_for(document_id: str, user: dict, journal_id: str | None, article_type: str | None):
    document, _ = get_accessible_document(document_id, user, capability="read")
    if not document["analysis_json"]:
        raise HTTPException(status_code=404, detail="Analyze the manuscript before running a compliance check.")
    journal_key = (journal_id or document["selected_journal_id"] or "nature").lower()
    try:
        journal = get_journal_rules(journal_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    analysis = json.loads(document["analysis_json"])
    source_format = (analysis.get("metadata") or {}).get("source_format")
    page_count = (analysis.get("metadata") or {}).get("page_count")
    report = build_compliance_report(
        analysis,
        journal,
        article_type=article_type,
        source_format=source_format,
        page_count=page_count,
    )
    return report, journal, analysis


@router.get("/documents/{document_id}/compliance")
async def get_compliance(
    document_id: str,
    journal_id: str | None = Query(default=None),
    article_type: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    report, _, _ = _compliance_for(document_id, user, journal_id, article_type)
    return report


@router.get("/documents/{document_id}/compliance/word-limit")
async def get_word_limit(
    document_id: str,
    journal_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    _, journal, analysis = _compliance_for(document_id, user, journal_id, None)
    return word_limit_analysis(analysis, journal)
