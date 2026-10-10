# Plagiarism training data

Store CSV, JSON, or JSONL samples here for supervised training and evaluation.
Each record should include these fields when available:

- source_document_id
- suspicious_document_id
- source_text
- suspicious_text
- label
- source_start
- source_end
- suspicious_start
- suspicious_end
- citation_context

The initial label should be 1 for suspicious or copied passage relationships and 0 for clean or unrelated text.
