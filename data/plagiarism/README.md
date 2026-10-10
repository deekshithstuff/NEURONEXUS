# Plagiarism training data

Only put authorized, provenance-preserving labeled pairs here. The `NEURONEXUS_TEST_DATASET_90`
bundle is synthetic end-to-end QA data, not plagiarism data and must not be used as a research
benchmark.

CSV, JSON array / `{ "data": [...] }`, and JSONL are accepted. Each record requires:

| Field | Meaning |
| --- | --- |
| `source_document_id` | Stable ID for the original/source document |
| `suspicious_document_id` | Stable ID for the compared document |
| `source_text` | Text passage from the source |
| `suspicious_text` | Corresponding passage from the compared document |
| `label` | `1` for an annotated suspicious/copied relationship; `0` for a documented non-match |

Optional fields include `source_start`, `source_end`, `suspicious_start`, `suspicious_end`,
`citation_context`, `source_group_id`, `document_group_id`, and `derivative_group_id`.
The training split builder links pairs sharing document IDs, explicitly supplied group IDs, or
identical normalized document text; connected groups never cross splits. Ambiguous or conflicting
labels must be resolved before training.

At least 12 valid labeled pairs and six independent document groups are required. Each train,
validation, and test split must contain both labels. The pipeline refuses to train if this cannot
be achieved. It does not create negative labels from unannotated text.

Example JSONL record:

```json
{"source_document_id":"source-001","suspicious_document_id":"document-009","source_text":"A documented source passage.","suspicious_text":"A corresponding passage.","label":1,"source_start":0,"source_end":31,"suspicious_start":125,"suspicious_end":149,"source_group_id":"study-family-001"}
```

## PAN-PC-11

The linked Zenodo record identifies PAN-PC-11 as CC-BY-4.0 and exposes two multipart RAR
files (approximately 1.7 GB total). This workspace does not contain those archives. Do not infer
labels from filenames or QA data. Inspect the archive's supplied documentation and XML annotations
after authorized download, then convert only verified source/suspicious offsets and labels into the
schema above. Preserve PAN document IDs and cite:

Potthast, M., Stein, B., Eiselt, A., Barrón-Cedeño, A., & Rosso, P. (2011). PAN Plagiarism Corpus
2011 (PAN-PC-11). Zenodo. https://doi.org/10.5281/zenodo.3250095

The record's license and dataset description are available at
<https://zenodo.org/records/3250095>. The current code intentionally does not guess the contents
or annotation semantics of an archive that is not present.
