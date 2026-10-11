from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.collaboration import service
from backend.collaboration.service import CollaborationError
from backend.security import get_current_user

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = "viewer"


class CollaboratorUpdate(BaseModel):
    role: str


class CommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    section_ref: str | None = None
    quote: str | None = None
    parent_id: str | None = None
    version_id: str | None = None


class ResolveRequest(BaseModel):
    resolved: bool = True


class ReviewRequest(BaseModel):
    decision: str
    comment: str | None = None
    version_id: str | None = None


class VersionRequest(BaseModel):
    label: str | None = None
    summary: str | None = None
    parent_version_id: str | None = None


def _fail(exc: CollaborationError) -> HTTPException:
    message = str(exc).lower()
    if "not found" in message:
        return HTTPException(status_code=404, detail=str(exc))
    if "permission" in message or "owner" in message or "manuscript owner" in message or "author" in message:
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/documents/{document_id}/collaborators")
async def list_collaborators(document_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.list_collaborators(document_id, user)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/collaborators")
async def invite_collaborator(document_id: str, request: InviteRequest, user: dict = Depends(get_current_user)):
    try:
        return service.invite_collaborator(document_id, user, request.email, request.role)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.patch("/documents/{document_id}/collaborators/{collaborator_id}")
async def update_collaborator(document_id: str, collaborator_id: str, request: CollaboratorUpdate, user: dict = Depends(get_current_user)):
    try:
        return service.update_collaborator(document_id, user, collaborator_id, request.role)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.delete("/documents/{document_id}/collaborators/{collaborator_id}")
async def remove_collaborator(document_id: str, collaborator_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.remove_collaborator(document_id, user, collaborator_id)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/collaboration/invitations")
async def list_invitations(user: dict = Depends(get_current_user)):
    return service.list_invitations(user)


@router.post("/collaboration/invitations/{collaborator_id}/accept")
async def accept_invitation(collaborator_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.accept_invitation(collaborator_id, user)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/collaboration/shared")
async def list_shared(user: dict = Depends(get_current_user)):
    return service.list_shared_documents(user)


@router.get("/documents/{document_id}/comments")
async def list_comments(
    document_id: str,
    version_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    try:
        return service.list_comments(document_id, user, version_id=version_id, page=page, page_size=page_size)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/comments")
async def add_comment(document_id: str, request: CommentRequest, user: dict = Depends(get_current_user)):
    try:
        return service.add_comment(document_id, user, request.model_dump())
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/comments/{comment_id}/resolve")
async def resolve_comment(document_id: str, comment_id: str, request: ResolveRequest, user: dict = Depends(get_current_user)):
    try:
        return service.resolve_comment(document_id, user, comment_id, request.resolved)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/documents/{document_id}/reviews")
async def list_reviews(document_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.list_review_decisions(document_id, user)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/reviews")
async def submit_review(document_id: str, request: ReviewRequest, user: dict = Depends(get_current_user)):
    try:
        return service.submit_review(document_id, user, request.model_dump())
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/documents/{document_id}/versions")
async def list_versions(
    document_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    try:
        return service.list_versions(document_id, user, page=page, page_size=page_size)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/versions")
async def create_version(document_id: str, request: VersionRequest, user: dict = Depends(get_current_user)):
    try:
        return service.create_version(document_id, user, request.model_dump())
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/documents/{document_id}/versions/diff")
async def diff_versions(
    document_id: str,
    from_version: str = Query(alias="from"),
    to_version: str = Query(alias="to"),
    user: dict = Depends(get_current_user),
):
    try:
        return service.diff_versions(document_id, user, from_version, to_version)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/documents/{document_id}/versions/{version_id}")
async def get_version(document_id: str, version_id: str, user: dict = Depends(get_current_user)):
    try:
        return service.get_version(document_id, version_id, user)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.post("/documents/{document_id}/versions/{version_id}/restore")
async def restore_version(document_id: str, version_id: str, request: VersionRequest, user: dict = Depends(get_current_user)):
    try:
        return service.restore_version(document_id, user, version_id, request.summary)
    except CollaborationError as exc:
        raise _fail(exc) from exc


@router.get("/collaboration/notifications")
async def list_notifications(unread_only: bool = Query(default=False), user: dict = Depends(get_current_user)):
    return service.list_notifications(user, unread_only=unread_only)


class MarkReadRequest(BaseModel):
    notification_id: str | None = None


@router.post("/collaboration/notifications/read")
async def mark_notifications_read(request: MarkReadRequest, user: dict = Depends(get_current_user)):
    return service.mark_notifications_read(user, request.notification_id)
