"""Collaborative review, comments, and manuscript version management.

Persistence-first: all collaboration state is stored in SQLite so it survives
reloads and is shared between accounts. Real-time transport is intentionally
not simulated; the API is authoritative.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.database import connection, fetch_all, fetch_one
from backend.security import (
    DOCUMENT_ROLES,
    collaborator_role,
    get_accessible_document,
    resolve_document_role,
)

ASSIGNABLE_ROLES = {"editor", "reviewer", "viewer"}
VALID_REVIEW_DECISIONS = {"approved", "revision_requested", "rejected", "comment"}
MAX_PAGE_SIZE = 100


class CollaborationError(ValueError):
    """Raised for invalid or unauthorized collaboration requests."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug_email(email: str) -> str:
    return email.strip().lower()


def _valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def _notify(user_id: str | None, document_id: str | None, kind: str, message: str) -> None:
    if not user_id:
        return
    with connection() as conn:
        conn.execute(
            "INSERT INTO notifications(id, user_id, document_id, kind, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"NTF-{uuid.uuid4().hex[:10].upper()}", user_id, document_id, kind, message, _now()),
        )


# ---------------------------------------------------------------------------
# Collaborators
# ---------------------------------------------------------------------------

def list_collaborators(document_id: str, user: dict) -> dict[str, Any]:
    document, role = get_accessible_document(document_id, user, capability="read")
    rows = fetch_all(
        "SELECT c.id, c.user_id, c.email, c.role, c.status, c.invited_by, c.created_at, "
        "u.name AS user_name "
        "FROM document_collaborators c LEFT JOIN users u ON u.id = c.user_id "
        "WHERE c.document_id = ? ORDER BY c.created_at, c.email",
        (document_id,),
    )
    owner = fetch_one("SELECT id, name, email FROM users WHERE id = ?", (document["user_id"],))
    collaborators = [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["user_name"],
            "email": row["email"],
            "role": row["role"],
            "status": row["status"],
            "invited_by": row["invited_by"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {
        "document_id": document_id,
        "owner": {"id": owner["id"], "name": owner["name"], "email": owner["email"], "role": "owner"} if owner else None,
        "collaborators": collaborators,
        "your_role": role,
    }


def invite_collaborator(document_id: str, user: dict, email: str, role: str) -> dict[str, Any]:
    document, _ = get_accessible_document(document_id, user, capability="manage_collaborators")
    normalized_role = (role or "viewer").strip().lower()
    if normalized_role not in ASSIGNABLE_ROLES:
        raise CollaborationError(f"Role must be one of: {', '.join(sorted(ASSIGNABLE_ROLES))}.")
    normalized_email = _slug_email(email)
    if not _valid_email(normalized_email):
        raise CollaborationError("Enter a valid email address.")
    if normalized_email == (user.get("email") or "").lower():
        raise CollaborationError("You already have access to this manuscript.")
    if fetch_one("SELECT id FROM users WHERE id = ? AND email = ?", (document["user_id"], normalized_email)):
        raise CollaborationError("The manuscript owner already has full access.")

    existing_user = fetch_one("SELECT id FROM users WHERE email = ?", (normalized_email,))
    status = "accepted" if existing_user else "pending"
    collaborator_id = f"COL-{uuid.uuid4().hex[:10].upper()}"
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO document_collaborators(id, document_id, user_id, email, role, status, invited_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    collaborator_id,
                    document_id,
                    existing_user["id"] if existing_user else None,
                    normalized_email,
                    normalized_role,
                    status,
                    user["id"],
                    _now(),
                ),
            )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise CollaborationError("This person is already listed as a collaborator.") from exc
        raise
    if existing_user:
        _notify(
            existing_user["id"],
            document_id,
            "collaboration_invite",
            f"You were added as a {normalized_role} on manuscript {document_id}.",
        )
    return {"collaborator_id": collaborator_id, "email": normalized_email, "role": normalized_role, "status": status}


def update_collaborator(document_id: str, user: dict, collaborator_id: str, role: str) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="manage_collaborators")
    normalized_role = (role or "").strip().lower()
    if normalized_role not in ASSIGNABLE_ROLES:
        raise CollaborationError(f"Role must be one of: {', '.join(sorted(ASSIGNABLE_ROLES))}.")
    row = fetch_one(
        "SELECT id FROM document_collaborators WHERE id = ? AND document_id = ?",
        (collaborator_id, document_id),
    )
    if not row:
        raise CollaborationError("Collaborator not found.")
    with connection() as conn:
        conn.execute("UPDATE document_collaborators SET role = ? WHERE id = ?", (normalized_role, collaborator_id))
    return {"collaborator_id": collaborator_id, "role": normalized_role}


def remove_collaborator(document_id: str, user: dict, collaborator_id: str) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="manage_collaborators")
    with connection() as conn:
        deleted = conn.execute(
            "DELETE FROM document_collaborators WHERE id = ? AND document_id = ?",
            (collaborator_id, document_id),
        ).rowcount
    if not deleted:
        raise CollaborationError("Collaborator not found.")
    return {"collaborator_id": collaborator_id, "removed": True}


def accept_invitation(collaborator_id: str, user: dict) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM document_collaborators WHERE id = ?", (collaborator_id,))
    if not row:
        raise CollaborationError("Invitation not found.")
    if (row["email"] or "").lower() != (user.get("email") or "").lower():
        raise CollaborationError("This invitation was issued to a different email address.")
    with connection() as conn:
        conn.execute(
            "UPDATE document_collaborators SET user_id = ?, status = 'accepted' WHERE id = ?",
            (user["id"], collaborator_id),
        )
        if row["invited_by"]:
            conn.execute(
                "INSERT INTO notifications(id, user_id, document_id, kind, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (f"NTF-{uuid.uuid4().hex[:10].upper()}", row["invited_by"], row["document_id"], "invitation_accepted", f"{user.get('name') or user.get('email')} accepted your collaboration invitation.", _now()),
            )
    return {"collaborator_id": collaborator_id, "status": "accepted", "document_id": row["document_id"], "role": row["role"]}


def list_invitations(user: dict) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT c.id, c.document_id, c.role, c.status, c.created_at, d.filename "
        "FROM document_collaborators c JOIN documents d ON d.id = c.document_id "
        "WHERE LOWER(c.email) = ? ORDER BY c.created_at DESC",
        ((user.get("email") or "").lower(),),
    )
    return {
        "invitations": [
            {
                "collaborator_id": row["id"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "role": row["role"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    }


def list_shared_documents(user: dict) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT d.id, d.filename, d.status, d.updated_at, c.role "
        "FROM document_collaborators c JOIN documents d ON d.id = c.document_id "
        "WHERE c.user_id = ? AND c.status = 'accepted' ORDER BY d.updated_at DESC, d.id",
        (user["id"],),
    )
    return {
        "documents": [
            {
                "document_id": row["id"],
                "filename": row["filename"],
                "status": row["status"],
                "updated_at": row["updated_at"],
                "role": row["role"],
            }
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# Comments and annotations
# ---------------------------------------------------------------------------

def list_comments(
    document_id: str,
    user: dict,
    *,
    version_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="read")
    page = max(1, int(page or 1))
    page_size = min(MAX_PAGE_SIZE, max(1, int(page_size or 50)))
    offset = (page - 1) * page_size
    query = "SELECT * FROM comments WHERE document_id = ?"
    params: list[Any] = [document_id]
    if version_id:
        query += " AND version_id = ?"
        params.append(version_id)
    query += " ORDER BY created_at, id LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    rows = fetch_all(query, params)
    total = fetch_one("SELECT COUNT(*) AS count FROM comments WHERE document_id = ?", (document_id,))["count"]
    users = {
        row["id"]: row["name"]
        for row in fetch_all("SELECT id, name FROM users")
    }
    comments = [
        {
            "id": row["id"],
            "parent_id": row["parent_id"],
            "author_id": row["author_id"],
            "author_name": users.get(row["author_id"]),
            "section_ref": row["section_ref"],
            "quote": row["quote"],
            "body": row["body"],
            "status": row["status"],
            "version_id": row["version_id"],
            "resolved_by": row["resolved_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
    return {"document_id": document_id, "comments": comments, "page": page, "page_size": page_size, "total": total}


def add_comment(document_id: str, user: dict, payload: dict) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="comment")
    body = (payload.get("body") or "").strip()
    if not body:
        raise CollaborationError("A comment body is required.")
    if len(body) > 5000:
        raise CollaborationError("Comments must be 5000 characters or fewer.")
    parent_id = payload.get("parent_id")
    if parent_id and not fetch_one("SELECT id FROM comments WHERE id = ? AND document_id = ?", (parent_id, document_id)):
        raise CollaborationError("The comment you are replying to was not found.")
    version_id = payload.get("version_id")
    comment_id = f"CMT-{uuid.uuid4().hex[:10].upper()}"
    with connection() as conn:
        conn.execute(
            "INSERT INTO comments(id, document_id, version_id, parent_id, author_id, section_ref, quote, body, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
            (
                comment_id,
                document_id,
                version_id,
                parent_id,
                user["id"],
                (payload.get("section_ref") or "").strip() or None,
                (payload.get("quote") or "").strip() or None,
                body,
                _now(),
                _now(),
            ),
        )
    document = fetch_one("SELECT user_id FROM documents WHERE id = ?", (document_id,))
    if document and document["user_id"] != user["id"]:
        _notify(document["user_id"], document_id, "comment", f"New comment on {document_id} from {user.get('name') or user.get('email')}.")
    return {"comment_id": comment_id, "status": "open"}


def resolve_comment(document_id: str, user: dict, comment_id: str, resolved: bool) -> dict[str, Any]:
    document, role = get_accessible_document(document_id, user, capability="comment")
    row = fetch_one("SELECT * FROM comments WHERE id = ? AND document_id = ?", (comment_id, document_id))
    if not row:
        raise CollaborationError("Comment not found.")
    if row["author_id"] != user["id"] and role not in {"owner", "admin"}:
        raise CollaborationError("Only the comment author or the manuscript owner can resolve this comment.")
    status = "resolved" if resolved else "open"
    with connection() as conn:
        conn.execute(
            "UPDATE comments SET status = ?, resolved_by = ?, updated_at = ? WHERE id = ?",
            (status, user["id"] if resolved else None, _now(), comment_id),
        )
    return {"comment_id": comment_id, "status": status}


# ---------------------------------------------------------------------------
# Review decisions
# ---------------------------------------------------------------------------

def list_review_decisions(document_id: str, user: dict) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="read")
    rows = fetch_all(
        "SELECT * FROM review_decisions WHERE document_id = ? ORDER BY created_at DESC, id",
        (document_id,),
    )
    users = {row["id"]: row["name"] for row in fetch_all("SELECT id, name FROM users")}
    decisions = [
        {
            "id": row["id"],
            "reviewer_id": row["reviewer_id"],
            "reviewer_name": users.get(row["reviewer_id"]),
            "decision": row["decision"],
            "comment": row["comment"],
            "version_id": row["version_id"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    latest = decisions[0] if decisions else None
    return {"document_id": document_id, "decisions": decisions, "latest": latest}


def submit_review(document_id: str, user: dict, payload: dict) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="review")
    decision = (payload.get("decision") or "").strip().lower()
    if decision not in VALID_REVIEW_DECISIONS:
        raise CollaborationError(f"Decision must be one of: {', '.join(sorted(VALID_REVIEW_DECISIONS))}.")
    version_id = payload.get("version_id")
    if version_id and not fetch_one("SELECT id FROM manuscript_versions WHERE id = ? AND document_id = ?", (version_id, document_id)):
        raise CollaborationError("The referenced manuscript version was not found.")
    decision_id = f"REV-{uuid.uuid4().hex[:10].upper()}"
    with connection() as conn:
        conn.execute(
            "INSERT INTO review_decisions(id, document_id, version_id, reviewer_id, decision, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (decision_id, document_id, version_id, user["id"], decision, (payload.get("comment") or "").strip() or None, _now()),
        )
    document = fetch_one("SELECT user_id FROM documents WHERE id = ?", (document_id,))
    if document and document["user_id"] != user["id"]:
        _notify(document["user_id"], document_id, "review", f"Review decision '{decision}' recorded on {document_id}.")
    return {"decision_id": decision_id, "decision": decision}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

def _version_text(analysis: dict | None) -> str:
    analysis = analysis or {}
    lines: list[str] = []
    if analysis.get("title"):
        lines.append(str(analysis["title"]))
    if analysis.get("abstract"):
        lines.append("Abstract:\n" + str(analysis["abstract"]))
    for section in analysis.get("sections") or []:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading") or section.get("type") or "Section"
        lines.append(f"{heading}:\n{section.get('content') or ''}")
    return "\n".join(lines)


def _content_hash(analysis: dict | None) -> str:
    return hashlib.sha256(_version_text(analysis).encode("utf-8")).hexdigest()


def ensure_initial_version(document) -> str | None:
    existing = fetch_one(
        "SELECT id FROM manuscript_versions WHERE document_id = ? ORDER BY version_number LIMIT 1",
        (document["id"],),
    )
    if existing:
        return existing["id"]
    if not document["analysis_json"]:
        return None
    analysis = json.loads(document["analysis_json"])
    version_id = f"VER-{uuid.uuid4().hex[:10].upper()}"
    with connection() as conn:
        conn.execute(
            "INSERT INTO manuscript_versions(id, document_id, version_number, author_id, label, change_summary, analysis_json, content_hash, created_at) "
            "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)",
            (
                version_id,
                document["id"],
                document["user_id"],
                "Initial analyzed version",
                "Baseline version created when the manuscript was first analyzed.",
                json.dumps(analysis),
                _content_hash(analysis),
                _now(),
            ),
        )
        conn.execute("UPDATE documents SET current_version_id = ? WHERE id = ?", (version_id, document["id"]))
    return version_id


def create_version(document_id: str, user: dict, payload: dict, analysis: dict | None = None) -> dict[str, Any]:
    document, _ = get_accessible_document(document_id, user, capability="manage_versions")
    if analysis is None:
        if not document["analysis_json"]:
            raise CollaborationError("Analyze the manuscript before creating a version.")
        analysis = json.loads(document["analysis_json"])
    parent_version_id = payload.get("parent_version_id") or document["current_version_id"]
    last = fetch_one(
        "SELECT MAX(version_number) AS max_number FROM manuscript_versions WHERE document_id = ?",
        (document_id,),
    )
    number = (last["max_number"] or 0) + 1
    version_id = f"VER-{uuid.uuid4().hex[:10].upper()}"
    summary = (payload.get("summary") or "Manuscript update").strip()[:500]
    label = (payload.get("label") or f"Version {number}").strip()[:120]
    with connection() as conn:
        conn.execute(
            "INSERT INTO manuscript_versions(id, document_id, version_number, author_id, parent_version_id, label, change_summary, analysis_json, content_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                version_id,
                document_id,
                number,
                user["id"],
                parent_version_id,
                label,
                summary,
                json.dumps(analysis),
                _content_hash(analysis),
                _now(),
            ),
        )
        conn.execute("UPDATE documents SET current_version_id = ? WHERE id = ?", (version_id, document_id))
    return {"version_id": version_id, "version_number": number, "label": label, "change_summary": summary}


def list_versions(document_id: str, user: dict, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    document, _ = get_accessible_document(document_id, user, capability="read")
    ensure_initial_version(document)
    page = max(1, int(page or 1))
    page_size = min(MAX_PAGE_SIZE, max(1, int(page_size or 50)))
    offset = (page - 1) * page_size
    rows = fetch_all(
        "SELECT id, version_number, author_id, parent_version_id, label, change_summary, content_hash, created_at "
        "FROM manuscript_versions WHERE document_id = ? ORDER BY version_number DESC LIMIT ? OFFSET ?",
        (document_id, page_size, offset),
    )
    total = fetch_one("SELECT COUNT(*) AS count FROM manuscript_versions WHERE document_id = ?", (document_id,))["count"]
    users = {row["id"]: row["name"] for row in fetch_all("SELECT id, name FROM users")}
    current = fetch_one("SELECT current_version_id FROM documents WHERE id = ?", (document_id,))
    versions = [
        {
            "version_id": row["id"],
            "version_number": row["version_number"],
            "author_id": row["author_id"],
            "author_name": users.get(row["author_id"]),
            "parent_version_id": row["parent_version_id"],
            "label": row["label"],
            "change_summary": row["change_summary"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {
        "document_id": document_id,
        "versions": versions,
        "page": page,
        "page_size": page_size,
        "total": total,
        "current_version_id": current["current_version_id"] if current else None,
    }


def get_version(document_id: str, version_id: str, user: dict) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="read")
    row = fetch_one(
        "SELECT * FROM manuscript_versions WHERE id = ? AND document_id = ?",
        (version_id, document_id),
    )
    if not row:
        raise CollaborationError("Version not found.")
    return {
        "version_id": row["id"],
        "document_id": row["document_id"],
        "version_number": row["version_number"],
        "label": row["label"],
        "change_summary": row["change_summary"],
        "created_at": row["created_at"],
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
    }


def diff_versions(document_id: str, user: dict, from_version_id: str, to_version_id: str) -> dict[str, Any]:
    get_accessible_document(document_id, user, capability="read")
    from_row = fetch_one("SELECT * FROM manuscript_versions WHERE id = ? AND document_id = ?", (from_version_id, document_id))
    to_row = fetch_one("SELECT * FROM manuscript_versions WHERE id = ? AND document_id = ?", (to_version_id, document_id))
    if not from_row or not to_row:
        raise CollaborationError("One or both versions were not found.")
    from_text = _version_text(json.loads(from_row["analysis_json"]) if from_row["analysis_json"] else {})
    to_text = _version_text(json.loads(to_row["analysis_json"]) if to_row["analysis_json"] else {})
    from_lines = from_text.splitlines()
    to_lines = to_text.splitlines()
    changes: list[dict] = []
    matcher = difflib.SequenceMatcher(a=from_lines, b=to_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append(
            {
                "type": tag,
                "from_lines": from_lines[i1:i2],
                "to_lines": to_lines[j1:j2],
            }
        )
    added = sum(len(change["to_lines"]) for change in changes if change["type"] in {"insert", "replace"})
    removed = sum(len(change["from_lines"]) for change in changes if change["type"] in {"delete", "replace"})
    return {
        "document_id": document_id,
        "from_version": {"version_id": from_row["id"], "version_number": from_row["version_number"]},
        "to_version": {"version_id": to_row["id"], "version_number": to_row["version_number"]},
        "changes": changes,
        "summary": {"blocks_changed": len(changes), "lines_added": added, "lines_removed": removed},
    }


def restore_version(document_id: str, user: dict, version_id: str, summary: str | None = None) -> dict[str, Any]:
    document, _ = get_accessible_document(document_id, user, capability="manage_versions")
    row = fetch_one(
        "SELECT * FROM manuscript_versions WHERE id = ? AND document_id = ?",
        (version_id, document_id),
    )
    if not row:
        raise CollaborationError("Version not found.")
    analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else None
    result = create_version(
        document_id,
        user,
        {
            "summary": summary or f"Restored from version {row['version_number']}.",
            "label": f"Restore of version {row['version_number']}",
            "parent_version_id": version_id,
        },
        analysis=analysis,
    )
    result["restored_from"] = version_id
    return result


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def list_notifications(user: dict, *, unread_only: bool = False) -> dict[str, Any]:
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: list[Any] = [user["id"]]
    if unread_only:
        query += " AND read = 0"
    query += " ORDER BY created_at DESC, id LIMIT 100"
    rows = fetch_all(query, params)
    return {
        "notifications": [
            {
                "id": row["id"],
                "document_id": row["document_id"],
                "kind": row["kind"],
                "message": row["message"],
                "read": bool(row["read"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    }


def mark_notifications_read(user: dict, notification_id: str | None = None) -> dict[str, Any]:
    with connection() as conn:
        if notification_id:
            conn.execute(
                "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user["id"]),
            )
        else:
            conn.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (user["id"],))
    return {"status": "ok"}


def resolve_role_label(role: str | None) -> str:
    return role or "none"
