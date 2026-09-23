# Research Publication Pipeline Backend

This backend implements the Half 1 publication engine for DOCX-driven manuscript preparation.

## Features

- DOCX upload validation and secure storage
- Document analysis for authors, abstract, keywords, and section extraction
- Figure, table, equation, citation, and reference extraction
- Citation/reference validation and duplicate detection
- Journal rule lookup and formatting metadata
- DOCX/PDF generation and submission package assembly

## Quick start

```bash
cd <repo-root>
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

## Main API endpoints

- POST /api/documents/upload
- GET /api/documents/{document_id}
- POST /api/documents/{document_id}/analyze
- GET /api/documents/{document_id}/structure
- POST /api/citations/check
- GET /api/citations/{document_id}
- GET /api/journals
- GET /api/journals/{journal_id}/rules
- POST /api/quality/analyze
- POST /api/novelty/analyze
- POST /api/methodology/analyze
- POST /api/contribution/analyze
- POST /api/writing/analyze
- POST /api/journal/match
- POST /api/improvement/generate
- POST /api/report/generate
- POST /api/documents/{document_id}/format
- POST /api/documents/{document_id}/generate
- GET /api/documents/{document_id}/download/docx
- GET /api/documents/{document_id}/download/pdf
- GET /api/documents/{document_id}/download/report
- GET /api/documents/{document_id}/download/zip

## Notes

- Only .docx files are accepted in this prototype.
- The SQLite database is created automatically on startup.
- Generated files are stored under the backend outputs directory.
