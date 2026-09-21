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
<<<<<<< HEAD
        "scope_topics": [
            "general science",
            "biomedical research",
            "computational biology",
            "genomics",
            "climate science",
            "environmental systems",
            "interdisciplinary science",
            "scientific discovery",
            "large-scale empirical studies",
            "materials science",
            "cell biology",
            "clinical research",
            "population health",
            "machine learning",
            "ai for science",
            "data-driven discovery",
            "remote sensing",
            "agriculture",
            "soil moisture",
            "environmental monitoring",
        ],
        "scope_aliases": {
            "machine learning": ["machine learning", "deep learning", "ai", "ml"],
            "environmental systems": ["soil moisture", "agriculture", "irrigation", "climate", "environmental monitoring"],
            "remote sensing": ["satellite imagery", "remote sensing", "crop disease", "earth observation"],
            "interdisciplinary science": ["smart systems", "cross-disciplinary", "applied ai", "data-driven discovery"],
        },
        "scope_summary": "Nature focuses on high-impact empirical and interdisciplinary science with strong translational and methodological novelty.",
=======
>>>>>>> 7824d8913e2157f6ebc06f3a0d20be405780bfa0
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
<<<<<<< HEAD
        "scope_topics": [
            "iot",
            "smart irrigation",
            "soil moisture",
            "esp32",
            "agriculture",
            "precision agriculture",
            "sensors",
            "embedded systems",
            "machine learning",
            "computer vision",
            "remote sensing",
            "crop disease",
            "signal processing",
            "edge computing",
            "smart systems",
            "wireless sensing",
            "deep learning",
            "telemetry",
            "systems engineering",
            "electronics",
            "applied ai",
            "precision agriculture",
            "agricultural monitoring",
        ],
        "scope_aliases": {
            "embedded systems": ["iot", "esp32", "sensors", "embedded systems", "wireless sensing", "telemetry"],
            "precision agriculture": ["smart irrigation", "soil moisture", "agriculture", "irrigation", "agricultural monitoring"],
            "applied computer vision": ["computer vision", "remote sensing", "crop disease", "satellite imagery"],
            "machine learning": ["machine learning", "deep learning", "ml", "ai"],
        },
        "scope_summary": "IEEE emphasizes engineering systems, applied AI, sensors, embedded systems, and computational methods with technical implementations.",
=======
>>>>>>> 7824d8913e2157f6ebc06f3a0d20be405780bfa0
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
