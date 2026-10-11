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
    user_id TEXT REFERENCES users(id),
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    working_path TEXT,
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
CREATE TABLE IF NOT EXISTS analysis_results (document_id TEXT NOT NULL, module TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(document_id, module), FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT,
    password_salt TEXT,
    google_sub TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plagiarism_scans (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'internal',
    engines_json TEXT,
    consent_external INTEGER NOT NULL DEFAULT 0,
    report_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS manuscript_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    author_id TEXT,
    parent_version_id TEXT,
    label TEXT,
    change_summary TEXT,
    analysis_json TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS document_collaborators (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    user_id TEXT,
    email TEXT NOT NULL COLLATE NOCASE,
    role TEXT NOT NULL DEFAULT 'viewer',
    status TEXT NOT NULL DEFAULT 'pending',
    invited_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, email),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT,
    parent_id TEXT,
    author_id TEXT NOT NULL,
    section_ref TEXT,
    quote TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS review_decisions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT,
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS conversion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    journal_id TEXT NOT NULL,
    article_type TEXT,
    status TEXT NOT NULL,
    output_dir TEXT,
    options_json TEXT,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS conversion_outputs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    journal_id TEXT NOT NULL,
    format TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES conversion_jobs(id)
);
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT,
    module TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_versions_document ON manuscript_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_comments_document ON comments(document_id);
CREATE INDEX IF NOT EXISTS idx_collaborators_document ON document_collaborators(document_id);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_document ON conversion_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_document ON analysis_snapshots(document_id);
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

def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(SCHEMA)
        document_columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
        if "user_id" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN user_id TEXT REFERENCES users(id)")
        if "working_path" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN working_path TEXT")
        _ensure_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'author'")
        _ensure_column(conn, "documents", "current_version_id", "TEXT")
        _ensure_column(conn, "conversion_jobs", "options_json", "TEXT")

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


def save_analysis_result(document_id: str, module: str, payload: dict[str, Any]) -> None:
    with connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS analysis_results ("
            "document_id TEXT NOT NULL, module TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY(document_id, module), FOREIGN KEY(document_id) REFERENCES documents(id))"
        )
        conn.execute(
            "INSERT OR REPLACE INTO analysis_results(document_id, module, payload_json, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (document_id, module, json.dumps(payload)),
        )
