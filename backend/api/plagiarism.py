from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.plagiarism import service
from backend.plagiarism.service import ScanError
from backend.security import create_download_token, get_current_user, get_download_user

router = APIRouter(prefix="/api")


class ScanRequest(BaseModel):
    engines: list[str] = Field(default_factory=list)
    provider: str = "internal"
    consent_external: bool = False


def _status_for(message: str) -> int:
    return 404 if "not found" in message.lower() else 400


@router.get("/plagiarism/status")
async def plagiarism_status(user: dict = Depends(get_current_user)):
    return service.scan_config()


@router.post("/documents/{document_id}/plagiarism/scan")
async def create_plagiarism_scan(
    document_id: str,
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    try:
        scan = service.start_scan(
            document_id,
            user,
            provider=request.provider,
            engines=request.engines,
            consent_external=request.consent_external,
        )
    except ScanError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc
    background_tasks.add_task(service.run_scan, scan["scan_id"])
    return scan


@router.get("/documents/{document_id}/plagiarism/scans")
async def list_plagiarism_scans(document_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.list_scans(document_id, user)
    except ScanError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc


@router.get("/plagiarism/scans/{scan_id}")
async def get_plagiarism_scan(scan_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.get_scan(scan_id, user)
    except ScanError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc


@router.get("/plagiarism/scans/{scan_id}/download-token")
async def create_plagiarism_download_token(scan_id: str, user: dict = Depends(get_current_user)):
    scan = service.get_scan(scan_id, user)
    token = create_download_token(user["id"], scan["document_id"], scope="plagiarism")
    return {
        "token": token,
        "expires_in_seconds": 300,
        "download_url": f"/api/plagiarism/scans/{scan_id}/download?token={token}",
    }


@router.get("/plagiarism/scans/{scan_id}/download")
async def download_plagiarism_report(scan_id: str, user: dict = Depends(get_download_user)):
    # The download token is bound to the owning document and expires quickly.
    try:
        filename, content = service.download_report(scan_id, user)
    except ScanError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
