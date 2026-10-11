"""Configurable structural requirements for research manuscript types.

These presets describe which research components are expected for a given
article type. They are intentionally conservative: a component is only treated
as required when the article type genuinely needs it. Journal profiles can add
or remove requirements on top of these presets.
"""

from __future__ import annotations

from copy import deepcopy

DEFAULT_ARTICLE_TYPE = "original_research"

# Components are identified by the canonical section keys used across the
# parser and analysis modules.
ARTICLE_TYPE_REQUIREMENTS: dict[str, dict] = {
    "original_research": {
        "label": "Original research article",
        "required_components": [
            "title",
            "abstract",
            "keywords",
            "introduction",
            "methodology",
            "results",
            "discussion",
            "conclusion",
            "references",
        ],
        "optional_components": [
            "related_work",
            "research_gap",
            "limitations",
            "future_work",
            "acknowledgments",
            "funding",
            "author_contributions",
            "conflict_of_interest",
            "data_availability",
            "ethics",
            "supplementary_material",
        ],
    },
    "review": {
        "label": "Review paper",
        "required_components": [
            "title",
            "abstract",
            "keywords",
            "introduction",
            "related_work",
            "discussion",
            "conclusion",
            "references",
        ],
        "optional_components": [
            "methodology",
            "results",
            "research_gap",
            "limitations",
            "future_work",
            "acknowledgments",
            "funding",
            "conflict_of_interest",
            "data_availability",
        ],
    },
    "conference_paper": {
        "label": "Conference paper",
        "required_components": [
            "title",
            "abstract",
            "keywords",
            "introduction",
            "methodology",
            "results",
            "conclusion",
            "references",
        ],
        "optional_components": [
            "related_work",
            "discussion",
            "limitations",
            "acknowledgments",
            "funding",
        ],
    },
    "short_communication": {
        "label": "Short communication",
        "required_components": [
            "title",
            "abstract",
            "introduction",
            "methodology",
            "results",
            "references",
        ],
        "optional_components": [
            "keywords",
            "discussion",
            "conclusion",
            "limitations",
        ],
    },
}

# Declaration labels that may be required by a journal profile.
DECLARATION_LABELS = {
    "funding": "Funding statement",
    "author_contributions": "Author contributions statement",
    "conflict_of_interest": "Conflict of interest declaration",
    "data_availability": "Data availability statement",
    "ethics": "Ethics statement",
    "acknowledgments": "Acknowledgements",
    "supplementary_material": "Supplementary material declaration",
}


def normalize_article_type(article_type: str | None) -> str:
    candidate = (article_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if candidate in ARTICLE_TYPE_REQUIREMENTS:
        return candidate
    aliases = {
        "research_article": "original_research",
        "research_paper": "original_research",
        "journal_article": "original_research",
        "transactions_journal_article": "original_research",
        "article": "original_research",
        "conference": "conference_paper",
        "proceedings": "conference_paper",
        "survey": "review",
        "systematic_review": "review",
        "literature_review": "review",
        "short_paper": "short_communication",
        "communication": "short_communication",
    }
    return aliases.get(candidate, DEFAULT_ARTICLE_TYPE)


def requirements_for(article_type: str | None) -> dict:
    return deepcopy(ARTICLE_TYPE_REQUIREMENTS[normalize_article_type(article_type)])


def available_article_types() -> list[dict]:
    return [
        {"id": key, "label": value["label"]}
        for key, value in ARTICLE_TYPE_REQUIREMENTS.items()
    ]
