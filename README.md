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
| 7. Plagiarism & similarity checking | Exact/near-exact matching against an identified corpus, optional semantic engine, optional external provider (`backend/plagiarism/`, Plagiarism tab) |

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

## Plagiarism check

The **Plagiarism** tab compares the manuscript against a clearly identified document collection,
preserves passage locations, and separates attributed overlap (quotations and cited text) from
suspected unattributed overlap. Similarity is presented as evidence to review, never as proof of
plagiarism; the report states this explicitly.

- **Internal corpus (default):** `backend/plagiarism/corpus/sources.json` ships synthetic exemplar
  texts. Point `PAPERPILOT_PLAGIARISM_CORPUS_DIR` at a directory of your own `.txt`/`.md`/`.json`
  sources to compare against a licensed collection. Manuscripts are never added to the corpus, so
  content is not shared between accounts.
- **Semantic engine (optional):** install `sentence-transformers` (`pip install "sentence-transformers>=3,<4"`).
  Semantic matches are labelled separately and are excluded from plagiarism counts because topical
  similarity alone is not evidence of plagiarism.
- **External provider (optional):** set `PAPERPILOT_PLAGIARISM_PROVIDER=copyleaks` plus
  `COPYLEAKS_EMAIL` and `COPYLEAKS_API_KEY`. Credentials stay on the backend and are never sent to the
  frontend. A scan using the external provider requires explicit user consent in the UI and fails
  cleanly on errors or timeouts without fabricating matches.

Endpoints (all require authentication; scans are scoped to the owning account):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/plagiarism/status` | Corpus, engine, and provider availability (no credentials) |
| `POST` | `/api/documents/{id}/plagiarism/scan` | Start a scan (`provider`, `engines`, `consent_external`) |
| `GET` | `/api/documents/{id}/plagiarism/scans` | List scans for a document |
| `GET` | `/api/plagiarism/scans/{scan_id}` | Scan status and report |
| `GET` | `/api/plagiarism/scans/{scan_id}/download` | Download the report as JSON |

## Typical workflow

1. **Upload** a `.docx` file from Dashboard or Upload.
2. Backend **parses** the manuscript and runs **citation checks**.
3. **AI modules** populate Quality, Novelty, Methodology, Journal fit, Improvements, and Report tabs.
4. On **Export**, click **Generate submission package**, then download **DOCX** and **PDF**.

## Tests

From the repository root:

```powershell
python -m pytest backend\tests -q
```

Frontend integration tests (Vitest + Testing Library):

```powershell
cd frontend
npm test
```

## Project layout

- `backend/` — FastAPI API, document engine, citations, formatting, plagiarism checker, PDF/DOCX generation
- `backend/plagiarism/` — corpus loading, lexical/semantic matching, feature extraction, classifier utilities, external provider, scan service
- `backend/training/` — dataset preparation, model training, and evaluation scripts for supervised plagiarism detection
- `models/plagiarism/` and `data/plagiarism/` — persisted model artifacts and labeled training data
- `frontend/` — PaperPilot UI (`src/App.jsx`, `src/PlagiarismPage.jsx`, `src/services/api.js`)

## Team / deliverables

- Working prototype: this repository
- PPT & abstract: prepare separately for submission
- Public GitHub: push this repo and share the link in your hackathon form
