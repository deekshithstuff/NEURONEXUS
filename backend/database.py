import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    status TEXT NOT NULL,
    selected_journal_id TEXT,
    analysis_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS document_sections (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS figures (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS tables (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS equations (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS citations (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS references_table (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS journals (id TEXT PRIMARY KEY, name TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal_rules (journal_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, FOREIGN KEY(journal_id) REFERENCES journals(id));
CREATE TABLE IF NOT EXISTS generated_documents (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, format TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(document_id) REFERENCES documents(id));
"""

@contextmanager
def connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(SCHEMA)

def execute(query: str, params: Iterable[Any] = ()) -> None:
    with connection() as conn:
        conn.execute(query, tuple(params))

def fetch_one(query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute(query, tuple(params)).fetchone()

def fetch_all(query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute(query, tuple(params)).fetchall()

def save_json_rows(table: str, document_id: str, rows: list[dict[str, Any]]) -> None:
    with connection() as conn:
        for index, payload in enumerate(rows, start=1):
            item_id = str(payload.get("id") or payload.get("section_id") or f"{table}-{index}")
            conn.execute(f"INSERT OR REPLACE INTO {table}(id, document_id, payload_json) VALUES (?, ?, ?)", (item_id, document_id, json.dumps(payload)))
