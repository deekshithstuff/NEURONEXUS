"""Per-user, persistent PDF reference corpus ingestion."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

import fitz

from backend.config import DATA_DIR, MAX_UPLOAD_BYTES
from backend.database import connection, fetch_all, fetch_one

MIN_INDEX_WORDS = 40
MAX_REFERENCE_PAGES = 500
MAX_REFERENCE_DOCUMENTS = 100
MAX_EXTRACTED_CHARS = 2_000_000
REFERENCE_DIR = DATA_DIR / "reference_corpus"


class ReferenceError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def ingest_pdf(filename: str, content: bytes, user: dict[str, str]) -> dict[str, Any]:
    safe_name = Path(filename or "reference.pdf").name[:255]
    if not safe_name.lower().endswith(".pdf") or not content.startswith(b"%PDF-"):
        raise ReferenceError("Upload a valid PDF reference document.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ReferenceError("Reference PDF exceeds the 15 MB upload limit.", 413)
    digest = hashlib.sha256(content).hexdigest()
    existing = fetch_one(
        "SELECT * FROM plagiarism_reference_documents WHERE user_id = ? AND sha256 = ?",
        (user["id"], digest),
    )
    if existing:
        return {**_serialize(existing), "duplicate_upload": True}
    document_count = fetch_one(
        "SELECT COUNT(*) AS count FROM plagiarism_reference_documents WHERE user_id = ?",
        (user["id"],),
    )["count"]
    if document_count >= MAX_REFERENCE_DOCUMENTS:
        raise ReferenceError(f"Each account can index up to {MAX_REFERENCE_DOCUMENTS} reference PDFs.", 413)

    reference_id = f"REF-{uuid.uuid4().hex[:12].upper()}"
    user_dir = REFERENCE_DIR / hashlib.sha256(user["id"].encode("utf-8")).hexdigest()[:24]
    user_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = user_dir / f"{reference_id}.pdf"
    pdf_path.write_bytes(content)
    try:
        try:
            extracted = _extract_pdf(content)
            extraction_error = None
        except ReferenceError as exc:
            if exc.status_code == 413:
                raise
            extracted = {"text": "", "page_spans": [], "page_count": 0, "word_count": 0, "title": None, "authors": [], "year": None}
            extraction_error = str(exc)
        near_duplicate = _find_near_duplicate(extracted["text"], user["id"])
        if extraction_error:
            status, error, duplicate_of = "failed", extraction_error, None
        elif near_duplicate:
            status = "duplicate"
            error = "This PDF is near-duplicate text of an existing reference and was not indexed."
            duplicate_of = near_duplicate
        elif extracted["word_count"] < MIN_INDEX_WORDS:
            status = "needs_ocr"
            error = "Too little selectable text was found. This PDF may be scanned; OCR is not configured."
            duplicate_of = None
        else:
            status, error, duplicate_of = "indexed", None, None
        title = extracted["title"] or _title_from_filename(safe_name)
        with connection() as conn:
            conn.execute(
                "INSERT INTO plagiarism_reference_documents "
                "(id, user_id, original_filename, pdf_path, sha256, title, authors_json, year, "
                "page_count, status, error, duplicate_of, text_content, page_spans_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (reference_id, user["id"], safe_name, str(pdf_path), digest, title,
                 json.dumps(extracted["authors"]), extracted["year"], extracted["page_count"],
                 status, error, duplicate_of, extracted["text"], json.dumps(extracted["page_spans"])),
            )
        return _get(reference_id, user["id"])
    except Exception:
        pdf_path.unlink(missing_ok=True)
        raise


def _extract_pdf(content: bytes) -> dict[str, Any]:
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise ReferenceError("Password-protected reference PDFs are not supported.")
            if not pdf.page_count:
                raise ReferenceError("The PDF contains no pages.")
            if pdf.page_count > MAX_REFERENCE_PAGES:
                raise ReferenceError(f"Reference PDFs are limited to {MAX_REFERENCE_PAGES} pages.", 413)
            page_lines: list[list[str]] = []
            for page in pdf:
                blocks = page.get_text("blocks", sort=True)
                paragraphs = []
                for block in blocks:
                    if len(block) <= 4:
                        continue
                    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", str(block[4]))
                    paragraph = re.sub(r"\s+", " ", text).strip()
                    if paragraph:
                        paragraphs.append(paragraph)
                page_lines.append(paragraphs)
            repeated = _repeated_furniture(page_lines)
            title = str(pdf.metadata.get("title") or "").strip() or None
            if title and title.casefold() in {"anonymous", "(anonymous)", "untitled"}:
                title = None
            author_line = str(pdf.metadata.get("author") or "").strip()
            authors = [
                item.strip()
                for item in re.split(r"\s*;\s*|\s+and\s+", author_line)
                if item.strip() and item.strip().casefold() not in {"anonymous", "(anonymous)"}
            ]
            creation_date = str(pdf.metadata.get("creationDate") or "")
            year_match = re.search(r"(?:19|20)\d{2}", creation_date)
            year = year_match.group(0) if year_match else None
    except ReferenceError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError, ValueError) as exc:
        raise ReferenceError("The PDF is corrupted, unreadable, or password-protected.") from exc

    full_text = ""
    page_spans: list[dict[str, int]] = []
    clean_pages: list[str] = []
    for page_number, lines in enumerate(page_lines, start=1):
        body = "\n\n".join(line for line in lines if line not in repeated)
        clean_pages.append(body)
    for page_number, body in enumerate(clean_pages, start=1):
        if full_text:
            full_text += "\n\n"
        start = len(full_text)
        full_text += body
        page_spans.append({"page": page_number, "start": start, "end": len(full_text)})
        if len(full_text) > MAX_EXTRACTED_CHARS:
            raise ReferenceError("Extracted PDF text exceeds the 2 MB indexing limit.", 413)
    return {
        "text": full_text,
        "page_spans": page_spans,
        "page_count": len(page_lines),
        "word_count": len(re.findall(r"\b[\w'-]+\b", full_text)),
        "title": title,
        "authors": authors,
        "year": year,
    }


def _repeated_furniture(pages: list[list[str]]) -> set[str]:
    if len(pages) < 2:
        return set()
    candidates: list[str] = []
    for lines in pages:
        candidates.extend(lines[:2])
        candidates.extend(lines[-2:])
    counts: dict[str, int] = {}
    for line in candidates:
        if len(line) < 4:
            continue
        counts[line] = counts.get(line, 0) + 1
    threshold = max(2, int(len(pages) * 0.6))
    return {line for line, count in counts.items() if count >= threshold}


def _find_near_duplicate(text: str, user_id: str, *, exclude_id: str | None = None) -> str | None:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if len(tokens) < MIN_INDEX_WORDS:
        return None
    shingles = _shingles(tokens)
    for row in fetch_all(
        "SELECT id, text_content FROM plagiarism_reference_documents "
        "WHERE user_id = ? AND status = 'indexed'",
        (user_id,),
    ):
        if row["id"] == exclude_id:
            continue
        other = re.findall(r"[a-z0-9]+", row["text_content"].lower())
        if not other:
            continue
        other_shingles = _shingles(other)
        if not shingles or not other_shingles:
            continue
        similarity = len(shingles & other_shingles) / len(shingles | other_shingles)
        if similarity >= 0.8:
            return row["id"]
    return None


def _shingles(tokens: list[str]) -> set[bytes]:
    width = 5
    if len(tokens) < width:
        return {hashlib.blake2b(" ".join(tokens).encode("utf-8"), digest_size=8).digest()}
    return {
        hashlib.blake2b(" ".join(tokens[index:index + width]).encode("utf-8"), digest_size=8).digest()
        for index in range(len(tokens) - width + 1)
    }


def list_documents(user: dict[str, str]) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT * FROM plagiarism_reference_documents WHERE user_id = ? ORDER BY created_at DESC, id",
        (user["id"],),
    )
    return {"documents": [_serialize(row) for row in rows]}


def get_document(reference_id: str, user: dict[str, str]) -> dict[str, Any]:
    return _get(reference_id, user["id"])


def _get(reference_id: str, user_id: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM plagiarism_reference_documents WHERE id = ? AND user_id = ?",
        (reference_id, user_id),
    )
    if row is None:
        raise ReferenceError("Reference document not found.", 404)
    return _serialize(row)


def delete_document(reference_id: str, user: dict[str, str]) -> None:
    row = fetch_one(
        "SELECT pdf_path FROM plagiarism_reference_documents WHERE id = ? AND user_id = ?",
        (reference_id, user["id"]),
    )
    if row is None:
        raise ReferenceError("Reference document not found.", 404)
    with connection() as conn:
        conn.execute(
            "DELETE FROM plagiarism_reference_documents WHERE id = ? AND user_id = ?",
            (reference_id, user["id"]),
        )
    _safe_pdf_path(row["pdf_path"]).unlink(missing_ok=True)


def reindex_document(reference_id: str, user: dict[str, str]) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM plagiarism_reference_documents WHERE id = ? AND user_id = ?",
        (reference_id, user["id"]),
    )
    if row is None:
        raise ReferenceError("Reference document not found.", 404)
    path = _safe_pdf_path(row["pdf_path"])
    if not path.is_file():
        raise ReferenceError("The stored PDF is missing; upload it again to re-index.", 409)
    try:
        extracted = _extract_pdf(path.read_bytes())
    except ReferenceError as exc:
        with connection() as conn:
            conn.execute("UPDATE plagiarism_reference_documents SET status='failed', error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (str(exc), reference_id))
        return _get(reference_id, user["id"])
    duplicate_of = _find_near_duplicate(extracted["text"], user["id"], exclude_id=reference_id)
    if duplicate_of:
        status = "duplicate"
        error = "This PDF is near-duplicate text of an existing reference and was not indexed."
    elif extracted["word_count"] >= MIN_INDEX_WORDS:
        status, error = "indexed", None
    else:
        status = "needs_ocr"
        error = "Too little selectable text was found. This PDF may be scanned; OCR is not configured."
    with connection() as conn:
        conn.execute(
            "UPDATE plagiarism_reference_documents SET title=?, authors_json=?, year=?, page_count=?, "
            "status=?, error=?, duplicate_of=?, text_content=?, page_spans_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (extracted["title"] or _title_from_filename(row["original_filename"]), json.dumps(extracted["authors"]), extracted["year"],
             extracted["page_count"], status, error, duplicate_of, extracted["text"], json.dumps(extracted["page_spans"]), reference_id),
        )
    return _get(reference_id, user["id"])


def load_sources(user_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(
        "SELECT * FROM plagiarism_reference_documents WHERE user_id = ? AND status = 'indexed' ORDER BY id",
        (user_id,),
    )
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "authors": json.loads(row["authors_json"] or "[]"),
            "year": row["year"],
            "url": None,
            "source_type": "user_reference_pdf",
            "filename": row["original_filename"],
            "page_spans": json.loads(row["page_spans_json"] or "[]"),
            "text": row["text_content"],
        }
        for row in rows
    ]


def _serialize(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "filename": row["original_filename"],
        "title": row["title"],
        "authors": json.loads(row["authors_json"] or "[]"),
        "year": row["year"],
        "page_count": row["page_count"],
        "status": row["status"],
        "error": row["error"],
        "duplicate_of": row["duplicate_of"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _safe_pdf_path(value: str) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(REFERENCE_DIR.resolve())
    except ValueError as exc:
        raise ReferenceError("Stored reference path is invalid.", 409) from exc
    return path


def _title_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").replace("-", " ").strip().title() or "Untitled reference"
