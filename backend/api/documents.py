from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import ALLOWED_EXTENSION, MAX_UPLOAD_BYTES, UPLOAD_DIR
from backend.database import connection, fetch_one, save_json_rows
from backend.document.parser import DocumentParser
from backend.journal.matcher import match_journal


def generate_document_id() -> str:
    while True:
        document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        if fetch_one("SELECT 1 FROM documents WHERE id = ?", (document_id,)) is None:
            return document_id

router = APIRouter(prefix="/api/documents")


class AnalysisRequest(BaseModel):
    journal_id: str | None = None


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    if not file.filename.lower().endswith(ALLOWED_EXTENSION):
        raise HTTPException(status_code=400, detail="Only DOCX files are supported in this prototype.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the maximum supported size.")

    document_id = generate_document_id()
    source_name = Path(file.filename).name
    safe_name = "".join(ch for ch in source_name if ch not in '\\/:*?\"<>|') or "document.docx"
    safe_path = UPLOAD_DIR / f"{document_id}_{safe_name}"
    if safe_path.exists():
        safe_path = UPLOAD_DIR / f"{document_id}_{uuid.uuid4().hex[:8]}_{safe_name}"
    safe_path.write_bytes(content)

    with connection() as conn:
        conn.execute(
            "INSERT INTO documents (id, filename, original_path, status, selected_journal_id) VALUES (?, ?, ?, ?, ?)",
            (document_id, file.filename, str(safe_path), "uploaded", None),
        )

    return {"document_id": document_id, "filename": file.filename, "status": "uploaded"}


@router.get("/{document_id}")
async def get_document(document_id: str):
    row = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"document_id": row["id"], "filename": row["filename"], "status": row["status"], "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None}


@router.post("/{document_id}/analyze")
async def analyze_document(document_id: str, request: AnalysisRequest):
    row = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    parser = DocumentParser()
    analysis = parser.parse(Path(row["original_path"]), document_id)
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
async def get_document_structure(document_id: str):
    row = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not row or not row["analysis_json"]:
        raise HTTPException(status_code=404, detail="Document structure is not available yet.")
    return json.loads(row["analysis_json"])
