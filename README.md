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
- **Lexical and exact evidence:** case/Unicode-normalized matching, word and character n-gram overlap,
  and corpus-fitted TF-IDF are reported as distinct evidence. The TF-IDF vectorizer is fitted during
  supervised model training and reused from its trusted artifact at inference.
- **Semantic engine (optional):** install `python -m pip install "sentence-transformers>=3,<4"` and
  set `PAPERPILOT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` if desired. This is a
  general-purpose pretrained embedding model, not a plagiarism-trained model. Semantic matches are
  labelled separately and are excluded from textual-overlap counts; if the dependency/model is
  unavailable, the engine reports that instead of returning substitute hash vectors.
- **Supervised classifier (optional):** train a logistic-regression model from authorized, labeled
  pairs with the commands below. Until a valid artifact exists, live scans mark classifier scoring
  unavailable. Classifier outputs are separate from exact/near-exact evidence and only score source
  passages retrieved from the identified corpus.
- **External provider (optional):** set `PAPERPILOT_PLAGIARISM_PROVIDER=copyleaks` plus
  `COPYLEAKS_EMAIL` and `COPYLEAKS_API_KEY`. Credentials stay on the backend and are never sent to the
  frontend. A scan using the external provider requires explicit user consent in the UI and fails
  cleanly on errors or timeouts without fabricating matches.

### Train and evaluate a supervised model (PowerShell)

Training does not run during document upload. Use labeled CSV, JSON, or JSONL passage pairs under
`data/plagiarism/` (see [data/plagiarism/README.md](data/plagiarism/README.md)). Labels must be
documented binary values: `1` for a suspicious/copied relationship, `0` for a documented non-match.
The split logic groups shared source/suspicious document IDs, explicitly related groups, and
identical normalized texts before splitting. It requires at least 12 pairs, six independent groups,
and both classes in train, validation, and test; there is no same-data evaluation fallback.

```powershell
cd E:\Project\NEURONEXUS
python -m pip install -r backend\requirements.txt
python -m backend.training.prepare_dataset data\plagiarism\pairs.jsonl --seed 42
python -m backend.training.train_classifier data\plagiarism\pairs.jsonl --output-dir models\plagiarism --seed 42
python -m backend.training.evaluate_classifier data\plagiarism\pairs.jsonl models\plagiarism\plagiarism_classifier.joblib --seed 42
```

Threshold selection is validation-only; test metrics are produced on the untouched independent test
split. The pipeline compares Logistic Regression to a most-frequent dummy baseline and a lexical
baseline. Reported positive scores are not calibrated probabilities. No classifier is trained or
evaluated by this repository until a real labeled dataset is supplied.

### PAN-PC-11 availability

The repository does not include PAN-PC-11 or claim to have trained on it. Its
[Zenodo record](https://zenodo.org/records/3250095) lists two multipart RAR files totaling about
1.7 GB under CC-BY-4.0. The archive and its annotations were not present here, so this project does
not assume their XML structure or label semantics. Download only if you are authorized to use it,
inspect its accompanying documentation, and convert verified annotated pairs to the documented
schema. Preserve original IDs and cite the dataset DOI
[`10.5281/zenodo.3250095`](https://doi.org/10.5281/zenodo.3250095).

Example download and extraction commands (requires 7-Zip installed and `7z.exe` available on `PATH`):

```powershell
New-Item -ItemType Directory -Force data\plagiarism\pan-pc-11 | Out-Null
Invoke-WebRequest "https://zenodo.org/records/3250095/files/pan-plagiarism-corpus-2011.part1.rar?download=1" -OutFile data\plagiarism\pan-pc-11\pan-plagiarism-corpus-2011.part1.rar
Invoke-WebRequest "https://zenodo.org/records/3250095/files/pan-plagiarism-corpus-2011.part2.rar?download=1" -OutFile data\plagiarism\pan-pc-11\pan-plagiarism-corpus-2011.part2.rar
Get-FileHash -Algorithm MD5 data\plagiarism\pan-pc-11\pan-plagiarism-corpus-2011.part1.rar
Get-FileHash -Algorithm MD5 data\plagiarism\pan-pc-11\pan-plagiarism-corpus-2011.part2.rar
7z x data\plagiarism\pan-pc-11\pan-plagiarism-corpus-2011.part1.rar -odata\plagiarism\pan-pc-11\extracted
```

Compare those hashes with part 1 `b2930f859497dd48ba5bb606d3f4a4f3` and part 2
`b23d86c17a47d2bfbdc4c314ea5810df` in Zenodo's file metadata. These downloads are large; verify the
license before use. PAN-PC-11
has not been downloaded, adapted, trained on, or evaluated by this repository.

Endpoints (all require authentication; scans are scoped to the owning account):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/plagiarism/status` | Corpus, engine, and provider availability (no credentials) |
| `POST` | `/api/documents/{id}/plagiarism/scan` | Start a scan (`provider`, `engines`, `consent_external`) |
| `GET` | `/api/documents/{id}/plagiarism/scans` | List scans for a document |
| `GET` | `/api/plagiarism/scans/{scan_id}` | Scan status and report |
| `GET` | `/api/plagiarism/scans/{scan_id}/download` | Download the report as JSON |

To configure a local comparison collection and optional trained artifact in PowerShell:

```powershell
$env:PAPERPILOT_PLAGIARISM_CORPUS_DIR = "E:\licensed-research-texts"
$env:PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH = "E:\Project\NEURONEXUS\models\plagiarism\plagiarism_classifier.joblib"
python -m uvicorn backend.main:app --reload --port 8000
```

Upload and analyze a document in the PaperPilot UI, then use **Start similarity scan** on its
Plagiarism tab. For direct API use, authenticate first and provide that account's analyzed document
ID; scan ownership checks and the same report format apply:

```powershell
$headers = @{ Authorization = "Bearer $accessToken" }
$body = @{ provider = "internal"; engines = @("lexical") } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/documents/$documentId/plagiarism/scan" -Headers $headers -ContentType "application/json" -Body $body
```

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
