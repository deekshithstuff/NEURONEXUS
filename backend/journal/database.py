import json
from pathlib import Path

from backend.database import fetch_all, fetch_one, connection

JOURNAL_LIBRARY = {
    "nature": {
        "journal_id": "nature",
        "journal_name": "Nature",
        "template_name": "Nature article",
        "page_size": "A4",
        "margins": {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        "columns": 1,
        "font": "Arial",
        "font_size": 11,
        "line_spacing": 1.15,
        "paragraph_spacing": 6,
        "citation_style": "numeric",
        "reference_style": "numbered",
        "heading_styles": {"1": "Heading 1", "2": "Heading 2", "3": "Heading 3"},
        "figure_rules": {"position": "float", "caption_style": "Figure"},
        "table_rules": {"position": "top", "caption_style": "Table"},
        "abstract_requirements": {"max_words": 250},
        "keyword_rules": {"required": True},
        "equation_rules": {"preserve_xml": True},
        "numbering_rules": {"bibliography": True},
        "word_limit": 4000,
    },
    "ieee": {
        "journal_id": "ieee",
        "journal_name": "IEEE",
        "template_name": "IEEE two-column",
        "page_size": "Letter",
        "margins": {"top": 0.75, "bottom": 0.75, "left": 0.6, "right": 0.6},
        "columns": 2,
        "font": "Times New Roman",
        "font_size": 10,
        "line_spacing": 1.0,
        "paragraph_spacing": 0,
        "citation_style": "numeric",
        "reference_style": "ieee",
        "heading_styles": {"1": "Heading 1", "2": "Heading 2", "3": "Heading 3"},
        "figure_rules": {"position": "top", "caption_style": "Figure"},
        "table_rules": {"position": "top", "caption_style": "Table"},
        "abstract_requirements": {"max_words": 200},
        "keyword_rules": {"required": False},
        "equation_rules": {"preserve_xml": True},
        "numbering_rules": {"section": True},
        "word_limit": 6000,
    },
}


def load_journal_rules() -> list[dict]:
    return [dict(payload) for payload in JOURNAL_LIBRARY.values()]


def seed_journals() -> None:
    with connection() as conn:
        for payload in load_journal_rules():
            conn.execute(
                "INSERT OR REPLACE INTO journals (id, name, payload_json) VALUES (?, ?, ?)",
                (payload["journal_id"], payload["journal_name"], json.dumps(payload)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO journal_rules (journal_id, payload_json) VALUES (?, ?)",
                (payload["journal_id"], json.dumps(payload)),
            )
