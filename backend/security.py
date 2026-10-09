from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import connection, fetch_one

SESSION_LIFETIME = timedelta(days=7)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return password_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, bytes.fromhex(salt))
    return secrets.compare_digest(candidate, password_hash)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = int((datetime.now(timezone.utc) + SESSION_LIFETIME).timestamp())
    with connection() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires_at),
        )
    return token


def public_user(row) -> dict[str, str]:
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Sign in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    row = fetch_one(
        "SELECT users.id, users.name, users.email FROM auth_sessions "
        "JOIN users ON users.id = auth_sessions.user_id "
        "WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?",
        (token_hash, int(datetime.now(timezone.utc).timestamp())),
    )
    if row is None:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return public_user(row)


def get_owned_document(document_id: str, user_id: str):
    document = fetch_one(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document
