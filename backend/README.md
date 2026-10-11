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
- POST /api/documents/{document_id}/conversions — start independent jobs for selected journal IDs
- GET /api/documents/{document_id}/conversions — list per-journal job states
- GET /api/conversions/{job_id} — retrieve status and compliance summary
- POST /api/conversions/{job_id}/retry — retry a failed job
- GET /api/conversions/{job_id}/download/{docx|pdf|compliance_json|compliance_pdf}

Conversion profiles and inherited base rules live in `backend/journal/profiles.json`. Add venue-specific values only when supported by a cited, dated official guideline; otherwise use `null` for unknown limits and keep the profile marked unverified. The current profiles are generic guidance, and citation-style transformation, exact page counts, and faithful PDF layout are not supported. Conversion jobs currently use FastAPI background tasks backed by SQLite; deployments that need crash-surviving work queues should replace this with a durable task broker.

## Notes

- Only .docx files are accepted in this prototype.
- The SQLite database is created automatically on startup.
- Generated files are stored under the backend outputs directory.
