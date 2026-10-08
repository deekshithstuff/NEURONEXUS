import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from backend.database import connection

RULES_PATH = Path(__file__).with_name("profiles.json")


def _merge(base: dict, overrides: dict) -> dict:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


@lru_cache(maxsize=1)
def load_journal_rules() -> list[dict]:
    configuration = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    bases = configuration.get("bases", {})

    def resolve_base(name: str | None, stack: tuple[str, ...] = ()) -> dict:
        if not name or name not in bases:
            return {}
        if name in stack:
            raise ValueError(f"Journal rule inheritance cycle: {name}")
        base = bases[name]
        parent = resolve_base(base.get("extends"), (*stack, name))
        return _merge(parent, base)

    profiles = []
    for profile in configuration.get("profiles", []):
        base = resolve_base(profile.get("extends"))
        resolved = _merge(base, profile)
        resolved.pop("extends", None)
        resolved.setdefault("abstract_requirements", {})
        resolved["abstract_requirements"].setdefault("max_words", resolved.get("abstract_formatting", {}).get("max_words"))
        resolved.setdefault("keyword_rules", {})
        resolved["keyword_rules"].setdefault("required", resolved.get("keyword_formatting", {}).get("required", False))
        resolved.pop("extends", None)
        profiles.append(resolved)
    return profiles


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
