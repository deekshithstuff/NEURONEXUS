from __future__ import annotations

import json
import fitz
import uuid
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.ai_service import generate_readiness_report
from backend.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from backend.database import connection, fetch_all, fetch_one, save_json_rows
from backend.document.parser import DocumentParser
from backend.journal.matcher import match_journal
from backend.security import get_current_user, get_owned_document


def generate_document_id() -> str:
    while True:
        document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        if fetch_one("SELECT 1 FROM documents WHERE id = ?", (document_id,)) is None:
            return document_id

router = APIRouter(prefix="/api/documents")


class AnalysisRequest(BaseModel):
    journal_id: str | None = None


class ReviewCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a DOCX or text-based PDF manuscript.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the maximum supported size.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if extension == ".docx":
                members = set(archive.namelist())
                if "[Content_Types].xml" not in members or "word/document.xml" not in members:
                    raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX document.")
    except (BadZipFile, OSError):
        if extension == ".docx":
            raise HTTPException(status_code=400, detail="The uploaded file is corrupted or is not a valid DOCX document.")
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF document.")
        try:
            with fitz.open(stream=content, filetype="pdf") as pdf:
                if pdf.is_encrypted:
                    raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported.")
        except fitz.FileDataError as exc:
            raise HTTPException(status_code=400, detail="The uploaded PDF is corrupted or unreadable.") from exc

    document_id = generate_document_id()
    source_name = Path(file.filename).name
    safe_name = "".join(ch for ch in source_name if ch not in '\\/:*?\"<>|') or "document.docx"
    safe_path = UPLOAD_DIR / f"{document_id}_{safe_name}"
    if safe_path.exists():
        safe_path = UPLOAD_DIR / f"{document_id}_{uuid.uuid4().hex[:8]}_{safe_name}"
    safe_path.write_bytes(content)

    with connection() as conn:
        conn.execute(
            "INSERT INTO documents (id, user_id, filename, original_path, status, selected_journal_id) VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, user["id"], file.filename, str(safe_path), "uploaded", None),
        )

    return {"document_id": document_id, "filename": file.filename, "status": "uploaded"}


@router.get("")
async def list_documents(user: dict = Depends(get_current_user)):
    rows = fetch_all(
        "SELECT id, filename, status, analysis_json, created_at, updated_at "
        "FROM documents WHERE user_id = ? ORDER BY updated_at DESC, id",
        (user["id"],),
    )
    documents = []
    for row in rows:
        analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else None
        documents.append(
            {
                "document_id": row["id"],
                "filename": row["filename"],
                "title": analysis.get("title") if analysis else row["filename"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return {"documents": documents}


@router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    rows = fetch_all(
        "SELECT id, analysis_json, selected_journal_id FROM documents "
        "WHERE user_id = ? ORDER BY updated_at DESC, id",
        (user["id"],),
    )
    scores = []
    dimension_totals: dict[str, int] = {}
    recommendation_count = 0
    high_priority_count = 0
    for row in rows:
        if not row["analysis_json"]:
            continue
        analysis = json.loads(row["analysis_json"])
        report = generate_readiness_report(
            row["id"], analysis, selected_journal=row["selected_journal_id"] or "nature"
        )
        scores.append(report["overall_readiness"])
        for name, score in report["scores"].items():
            dimension_totals[name] = dimension_totals.get(name, 0) + score
        recommendations = report["recommendations"]
        recommendation_count += len(recommendations)
        high_priority_count += sum(item["category"] in {"CRITICAL", "HIGH"} for item in recommendations)
    return {
        "manuscript_count": len(rows),
        "analyzed_count": len(scores),
        "readiness_average": round(sum(scores) / len(scores)) if scores else None,
        "open_suggestions": recommendation_count,
        "high_priority_suggestions": high_priority_count,
        "recent_document_id": rows[0]["id"] if rows else None,
        "dimension_averages": {
            name: round(total / len(scores)) for name, total in dimension_totals.items()
        },
    }


@router.get("/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    row = get_owned_document(document_id, user["id"])
    return {"document_id": row["id"], "filename": row["filename"], "status": row["status"], "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None}


@router.post("/{document_id}/analyze")
async def analyze_document(
    document_id: str,
    request: AnalysisRequest,
    user: dict = Depends(get_current_user),
):
    row = get_owned_document(document_id, user["id"])
    parser = DocumentParser()
    try:
        source_path = Path(row["original_path"])
        if source_path.suffix.lower() == ".pdf":
            analysis = parser.parse_pdf(source_path, document_id)
        else:
            analysis = parser.parse(source_path, document_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc) or "The DOCX could not be parsed.") from exc
    with connection() as conn:
        conn.execute(
            "UPDATE documents SET analysis_json = ?, status = ?, selected_journal_id = ? WHERE id = ?",
            (json.dumps(analysis.model_dump()), "analyzed", request.journal_id or match_journal(analysis.model_dump()).get("journal_id"), document_id),
        )
    save_json_rows("document_sections", document_id, [section.model_dump() for section in analysis.sections])
    save_json_rows("figures", document_id, [figure.model_dump() for figure in analysis.figures])
    save_json_rows("tables", document_id, [table.model_dump() for table in analysis.tables])
    save_json_rows("equations", document_id, [equation.model_dump() for equation in analysis.equations])
    save_json_rows("citations", document_id, [citation.model_dump() for citation in analysis.citations])
    save_json_rows("references_table", document_id, [reference.model_dump() for reference in analysis.references])
    return analysis.model_dump()


@router.get("/{document_id}/structure")
async def get_document_structure(document_id: str, user: dict = Depends(get_current_user)):
    row = fetch_one(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user["id"]),
    )
    if not row or not row["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document structure is not available yet.")
    return json.loads(row["analysis_json"])


@router.get("/{document_id}/analysis/{module}")
async def get_saved_analysis(
    document_id: str,
    module: str,
    user: dict = Depends(get_current_user),
):
    if not fetch_one(
        "SELECT 1 FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user["id"]),
    ):
        raise HTTPException(status_code=404, detail="Document not found.")
    result = fetch_one(
        "SELECT payload_json, updated_at FROM analysis_results WHERE document_id = ? AND module = ?",
        (document_id, module),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result is not available yet.")
    return {"document_id": document_id, "module": module, "updated_at": result["updated_at"], "result": json.loads(result["payload_json"])}


@router.get("/{document_id}/versions")
async def get_document_versions(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    rows = fetch_all(
        "SELECT id, version_number, journal_id, artifacts_json, created_at "
        "FROM document_versions WHERE document_id = ? ORDER BY version_number DESC",
        (document_id,),
    )
    return {
        "document_id": document_id,
        "versions": [
            {
                "id": row["id"],
                "version_number": row["version_number"],
                "journal_id": row["journal_id"],
                "files": sorted(json.loads(row["artifacts_json"]).keys()),
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }


@router.get("/{document_id}/review-comments")
async def get_review_comments(document_id: str, user: dict = Depends(get_current_user)):
    get_owned_document(document_id, user["id"])
    rows = fetch_all(
        "SELECT review_comments.id, review_comments.content, review_comments.created_at, users.name "
        "FROM review_comments JOIN users ON users.id = review_comments.user_id "
        "WHERE review_comments.document_id = ? ORDER BY review_comments.created_at DESC, review_comments.id",
        (document_id,),
    )
    return {"document_id": document_id, "comments": [
        {"id": row["id"], "content": row["content"], "author": row["name"], "created_at": row["created_at"]}
        for row in rows
    ]}


@router.post("/{document_id}/review-comments", status_code=201)
async def add_review_comment(
    document_id: str,
    request: ReviewCommentRequest,
    user: dict = Depends(get_current_user),
):
    get_owned_document(document_id, user["id"])
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Review note cannot be blank.")
    comment_id = str(uuid.uuid4())
    with connection() as conn:
        conn.execute(
            "INSERT INTO review_comments(id, document_id, user_id, content) VALUES (?, ?, ?, ?)",
            (comment_id, document_id, user["id"], content),
        )
    return {"id": comment_id, "content": content, "author": user["name"]}
