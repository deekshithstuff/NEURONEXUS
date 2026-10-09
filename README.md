# PaperPilot (NeuroNexus)

AI-powered **Research Paper Automation & Journal Readiness Platform** — upload a DOCX or text-based PDF manuscript, analyze structure and citations, run journal-fit and quality checks, and export a formatted submission package (DOCX + PDF + readiness report).

## Hackathon feature coverage

| Requirement | Implementation |
|-------------|----------------|
| 1. Research document analysis | DOCX and text-based PDF upload, section/citation/reference extraction (`backend/document/`) |
| 2. Journal template automation | Nature & IEEE rules, formatting engine (`backend/formatting/`, `POST .../format`) |
| 3. Citation & reference management | Parser, validator, duplicate detection (`backend/citation/`) |
| 4. AI journal readiness & quality | Quality, novelty, methodology, writing, journal match, report (`backend/ai_service.py`, `backend/api/ai.py`) |
| 5. Publication-ready document generation | DOCX generator with journal styling (`backend/generator/`) |
| 6. Export & submission package | DOCX/PDF download + submission folder (`POST .../generate`, download endpoints) |

## Quick start

### Backend (FastAPI)

```powershell
cd <repo-root>
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Create an account in the app with your name, email, and a password of at least 10 characters. Each account can access only its own uploaded manuscripts. Manuscript uploads support DOCX and text-based PDF files (up to 15 MB); scanned/image-only PDFs need OCR and are not supported. PDF text extraction may not preserve the original visual layout, figures, or tables in the reconstructed export. To enable Google sign-in, create a Google Identity Services Web OAuth client, add the app's authorized JavaScript origin (for example `http://localhost:5173` or `http://127.0.0.1:5173`), then set `GOOGLE_CLIENT_ID` in the repository-root `.env` file and restart the backend. The Google button is unavailable until this is configured.

### Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in or create an account — the dev server proxies `/api` to the backend.

Optional: set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` if not using the proxy.

## Typical workflow

1. **Upload** a `.docx` file from Dashboard or Upload.
2. Backend **parses** the manuscript and runs **citation checks**.
3. **AI modules** populate Quality, Novelty, Methodology, Journal fit, Improvements, and Report tabs.
4. On **Export**, click **Generate submission package**, then download **DOCX** and **PDF**.

## Tests

From the repository root:

```powershell
python -m pytest backend\tests\test_pipeline.py -q
```

## Project layout

- `backend/` — FastAPI API, document engine, citations, formatting, PDF/DOCX generation
- `frontend/` — PaperPilot UI (`src/App.jsx`, `src/services/api.js`)

## Team / deliverables

- Working prototype: this repository
- PPT & abstract: prepare separately for submission
- Public GitHub: push this repo and share the link in your hackathon form
