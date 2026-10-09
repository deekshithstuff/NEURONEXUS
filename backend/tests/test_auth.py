from uuid import uuid4

from fastapi.testclient import TestClient

from backend.database import connection
from backend.main import app


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
