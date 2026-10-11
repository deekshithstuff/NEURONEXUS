"""Apply user-approved text changes to a DOCX source document.

Only the exact, whitespace-flexible occurrences of the accepted original text
are replaced. If a change cannot be matched, the source is left untouched for
that change so no content is silently lost.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from backend.text_utils import sanitize_xml_text


def apply_changes_to_source(source_path: str | Path, output_path: str | Path, applied_changes: list[dict]) -> Path:
    doc = Document(source_path)
    for change in applied_changes:
        original = change.get("original") or ""
        suggested = sanitize_xml_text(change.get("suggested") or "")
        if not original or not suggested:
            continue
        pattern = re.compile(
            r"\s+".join(re.escape(part) for part in original.split() if part),
            flags=re.IGNORECASE,
        )
        for paragraph in doc.paragraphs:
            match = pattern.search(paragraph.text)
            if not match:
                continue
            for run in paragraph.runs:
                if run.text and run.text.strip() and pattern.search(run.text):
                    run.text = pattern.sub(suggested, run.text, count=1)
                    match = None
                    break
            if match is not None:
                start, end = match.span()
                paragraph.runs[0].text = paragraph.text[:start] + suggested + paragraph.text[end:]
                for extra_run in paragraph.runs[1:]:
                    extra_run.text = ""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return output
