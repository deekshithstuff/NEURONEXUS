from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.journal.database import load_journal_rules
from backend.journal.rules import get_journal_rules

router = APIRouter(prefix="/api/journals")


@router.get("")
async def list_journals():
    return {"journals": load_journal_rules()}


@router.get("/{journal_id}/rules")
async def get_rules(journal_id: str):
    try:
        return {"journal_id": journal_id, "rules": get_journal_rules(journal_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
