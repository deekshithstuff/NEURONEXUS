from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import Response

from backend.analytics.service import build_dashboard
from backend.security import get_current_user

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


@router.get("/documents/{document_id}/analytics")
async def get_analytics(
    document_id: str,
    journal_id: str | None = Query(default=None),
    version_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    try:
        return build_dashboard(document_id, user, journal_id=journal_id, version_id=version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/documents/{document_id}/analytics/export")
async def export_analytics(
    document_id: str,
    journal_id: str | None = Query(default=None),
    version_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    try:
        dashboard = build_dashboard(document_id, user, journal_id=journal_id, version_id=version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = f"paperpilot-analytics-{document_id}.json"
    return Response(
        content=json.dumps(dashboard, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
