from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from backend.conversion import service
from backend.conversion.service import ConversionError
from backend.security import get_current_user

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


class ConversionRequest(BaseModel):
    journal_ids: list[str] = Field(min_length=1)
    article_type: str | None = None
    approved_changes: list[dict] = Field(default_factory=list)


def _status_for(message: str) -> int:
    lowered = message.lower()
    if "not found" in lowered:
        return 404
    if "permission" in lowered:
        return 403
    return 400


@router.post("/documents/{document_id}/conversions")
async def create_conversions(
    document_id: str,
    request: ConversionRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    try:
        jobs = service.start_conversion(
            document_id,
            user,
            request.journal_ids,
            article_type=request.article_type,
            approved_changes=request.approved_changes,
        )
    except ConversionError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc
    for job in jobs:
        background_tasks.add_task(service.run_conversion, job["job_id"])
    return {"document_id": document_id, "jobs": jobs}


@router.get("/documents/{document_id}/conversions")
async def list_conversions(document_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.list_jobs(document_id, user)
    except ConversionError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc


@router.get("/conversions/{job_id}")
async def get_conversion(job_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.get_job(job_id, user)
    except ConversionError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc


@router.get("/conversions/{job_id}/download/{file_format}")
async def download_conversion(job_id: str, file_format: str, user: dict = Depends(get_current_user)):
    try:
        filename, target, media = service.job_output_path(job_id, user, file_format)
    except ConversionError as exc:
        raise HTTPException(status_code=_status_for(str(exc)), detail=str(exc)) from exc
    return FileResponse(target, media_type=media, filename=filename)
