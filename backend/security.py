from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import connection, fetch_one

SESSION_LIFETIME = timedelta(days=7)
DOWNLOAD_TOKEN_LIFETIME = timedelta(minutes=5)
bearer_scheme = HTTPBearer(auto_error=False)

# Document-scoped roles and the capabilities granted by each role.
DOCUMENT_ROLES = {"owner", "editor", "reviewer", "viewer"}
ROLE_CAPABILITIES = {
    "owner": {"read", "comment", "review", "edit", "manage_collaborators", "generate", "convert", "manage_versions"},
    "admin": {"read", "comment", "review", "edit", "manage_collaborators", "generate", "convert", "manage_versions"},
    "editor": {"read", "comment", "review", "edit", "generate", "convert", "manage_versions"},
    "reviewer": {"read", "comment", "review"},
    "viewer": {"read"},
}


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


def create_download_token(user_id: str, document_id: str, scope: str = "download") -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = int((datetime.now(timezone.utc) + DOWNLOAD_TOKEN_LIFETIME).timestamp())
    with connection() as conn:
        conn.execute(
            "INSERT INTO download_tokens (id, document_id, user_id, token_hash, expires_at, scope) VALUES (?, ?, ?, ?, ?, ?)",
            (f"download-{secrets.token_hex(8)}", document_id, user_id, token_hash, expires_at, scope),
        )
    return token


def validate_download_token(document_id: str, token: str | None, scope: str) -> dict[str, str] | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = fetch_one(
        "SELECT users.id, users.name, users.email FROM download_tokens "
        "JOIN users ON users.id = download_tokens.user_id "
        "WHERE download_tokens.document_id = ? AND download_tokens.token_hash = ? "
        "AND download_tokens.expires_at > ? AND download_tokens.scope = ?",
        (document_id, token_hash, int(datetime.now(timezone.utc).timestamp()), scope),
    )
    return public_user(row) if row else None


def public_user(row) -> dict[str, str]:
    user = {"id": row["id"], "name": row["name"], "email": row["email"]}
    try:
        user["role"] = row["role"] or "author"
    except (IndexError, KeyError):
        user["role"] = "author"
    return user


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
        "SELECT users.id, users.name, users.email, users.role FROM auth_sessions "
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


def get_download_user(
    request: Request,
    document_id: str | None = None,
    scan_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = None,
) -> dict[str, str]:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        user = get_current_user(credentials)
        if user:
            return user

    resolved_document_id = document_id
    if resolved_document_id is None and scan_id is not None:
        row = fetch_one("SELECT document_id FROM plagiarism_scans WHERE id = ?", (scan_id,))
        if row is not None:
            resolved_document_id = row["document_id"]

    if resolved_document_id is None:
        raise HTTPException(
            status_code=401,
            detail="Download authorization expired or is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scope = "plagiarism" if "/plagiarism/" in request.url.path else request.url.path.rsplit("/", 1)[-1]
    download_user = validate_download_token(resolved_document_id, token, scope)
    if download_user is not None:
        return download_user

    raise HTTPException(
        status_code=401,
        detail="Download authorization expired or is invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_owned_document(document_id: str, user_id: str):
    document = fetch_one(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


def collaborator_role(document_id: str, user_id: str) -> str | None:
    row = fetch_one(
        "SELECT role FROM document_collaborators "
        "WHERE document_id = ? AND user_id = ? AND status = 'accepted'",
        (document_id, user_id),
    )
    return row["role"] if row else None


def resolve_document_role(document, user: dict) -> str | None:
    if document is None:
        return None
    if document["user_id"] == user.get("id"):
        return "owner"
    if (user.get("role") or "").lower() == "admin":
        return "admin"
    return collaborator_role(document["id"], user.get("id") or "")


def has_capability(role: str | None, capability: str) -> bool:
    return bool(role) and capability in ROLE_CAPABILITIES.get(role, set())


def require_capability(role: str | None, capability: str) -> None:
    if not has_capability(role, capability):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")


def get_accessible_document(document_id: str, user: dict, *, capability: str = "read"):
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    role = resolve_document_role(document, user)
    if role is None:
        # Return 404 rather than 403 so document existence is not disclosed.
        raise HTTPException(status_code=404, detail="Document not found.")
    if not has_capability(role, capability):
        raise HTTPException(status_code=403, detail="You do not have permission to access this document action.")
    return document, role
