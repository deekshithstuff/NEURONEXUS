from uuid import uuid4

from fastapi.testclient import TestClient

from backend.config import OUTPUT_DIR
from backend.database import connection
from backend.main import app
from backend.security import create_download_token


def register(client: TestClient, email: str, name: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_account_authentication_and_private_manuscripts():
    with TestClient(app) as client:
        assert client.get("/api/documents").status_code == 401

        email = f"researcher-{uuid4()}@example.test"
        first_account = register(client, email, "Researcher One")
        first_user = first_account["user"]
        assert "password" not in first_user
        first_token = first_account["access_token"]
        first_headers = {"Authorization": f"Bearer {first_token}"}

        document_id = f"DOC-{uuid4().hex[:8].upper()}"
        with connection() as conn:
            conn.execute(
                "INSERT INTO documents (id, user_id, filename, original_path, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (document_id, first_user["id"], "private.docx", "", "uploaded"),
            )

        assert client.get("/api/documents", headers=first_headers).json()["documents"][0]["filename"] == "private.docx"
        assert client.get(f"/api/documents/{document_id}", headers=first_headers).status_code == 200

        second_account = register(client, f"other-{uuid4()}@example.test", "Researcher Two")
        second_headers = {"Authorization": f"Bearer {second_account['access_token']}"}
        assert client.get("/api/documents", headers=second_headers).json()["documents"] == []
        assert client.get(f"/api/documents/{document_id}", headers=second_headers).status_code == 404
        assert client.get(f"/api/documents/{document_id}/download/docx", headers=second_headers).status_code == 404

        duplicate = client.post(
            "/api/auth/register",
            json={"name": "Duplicate", "email": email.upper(), "password": "correct-horse-battery"},
        )
        assert duplicate.status_code == 409

        login = client.post(
            "/api/auth/login",
            json={"email": email.upper(), "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        login_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/auth/me", headers=login_headers).json()["user"]["id"] == first_user["id"]

        logout = client.post("/api/auth/logout", headers=login_headers)
        assert logout.status_code == 200
        assert client.get("/api/auth/me", headers=login_headers).status_code == 401
        assert client.post(
            "/api/auth/login",
            json={"email": email, "password": "incorrect-horse-battery"},
        ).status_code == 401


def test_download_route_accepts_query_token_for_direct_browser_downloads():
    with TestClient(app) as client:
        email = f"download-{uuid4()}@example.test"
        account = register(client, email, "Direct Download User")
        document_id = f"DOC-{uuid4().hex[:8].upper()}"
        target_dir = OUTPUT_DIR / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / "final_manuscript.docx"
        target_path.write_bytes(b"PK\x03\x04fake-docx")

        with connection() as conn:
            conn.execute(
                "INSERT INTO documents (id, user_id, filename, original_path, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (document_id, account["user"]["id"], "direct-download.docx", str(target_path), "generated"),
            )

        token = create_download_token(account["user"]["id"], document_id, scope="docx")
        response = client.get(f"/api/documents/{document_id}/download/docx?token={token}")
        assert response.status_code == 200, response.text
        assert "attachment" in response.headers["content-disposition"].lower()
        assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        expired = create_download_token(account["user"]["id"], document_id, scope="docx")
        with connection() as conn:
            conn.execute(
                "UPDATE download_tokens SET expires_at = ? WHERE token_hash = ?",
                (0, __import__('hashlib').sha256(expired.encode()).hexdigest()),
            )
        expired_response = client.get(f"/api/documents/{document_id}/download/docx?token={expired}")
        assert expired_response.status_code == 401, expired_response.text

        wrong_scope = create_download_token(account["user"]["id"], document_id, scope="pdf")
        wrong_scope_response = client.get(f"/api/documents/{document_id}/download/docx?token={wrong_scope}")
        assert wrong_scope_response.status_code == 401, wrong_scope_response.text

        second_account = register(client, f"other-download-{uuid4()}@example.test", "Other Download User")
        other_headers = {"Authorization": f"Bearer {second_account['access_token']}"}
        unauthorized_response = client.get(f"/api/documents/{document_id}/download/docx", headers=other_headers)
        assert unauthorized_response.status_code == 404, unauthorized_response.text

        success_token = create_download_token(account["user"]["id"], document_id, scope="docx")
        success_response = client.get(f"/api/documents/{document_id}/download/docx?token={success_token}")
        assert success_response.status_code == 200, success_response.text
