from __future__ import annotations

import os
import re
import sqlite3
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.database import connection, fetch_one
from backend.security import (
    bearer_scheme,
    create_session,
    get_current_user,
    hash_password,
    public_user,
    verify_password,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter(prefix="/api/auth")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=80)


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return normalized


def _session_response(user_row) -> dict:
    return {"access_token": create_session(user_row["id"]), "user": public_user(user_row)}


@router.get("/config")
async def auth_config():
    return {"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")}


@router.post("/register")
async def register(request: Registration):
    email = _normalize_email(request.email)
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Enter your name.")
    password_hash, password_salt = hash_password(request.password)
    user_id = str(uuid.uuid4())
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, password_salt) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, name, email, password_hash, password_salt),
            )
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
        raise
    user = fetch_one("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    return _session_response(user)


@router.post("/login")
async def login(request: Credentials):
    email = _normalize_email(request.email)
    user = fetch_one(
        "SELECT id, name, email, password_hash, password_salt FROM users WHERE email = ?",
        (email,),
    )
    if user is None or not user["password_hash"] or not user["password_salt"]:
        hash_password(request.password, bytes(16))
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not verify_password(request.password, user["password_hash"], user["password_salt"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _session_response(user)


@router.post("/google")
async def google_login(request: GoogleCredential):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured yet.")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": request.credential},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google sign-in could not be verified. Please try again.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified.")

    claims = response.json()
    if (
        claims.get("aud") != client_id
        or claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
        or claims.get("email_verified") not in {True, "true"}
        or not claims.get("email")
        or not claims.get("sub")
    ):
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified.")

    email = _normalize_email(claims["email"])
    user = fetch_one(
        "SELECT id, name, email, google_sub FROM users WHERE google_sub = ? OR email = ?",
        (claims["sub"], email),
    )
    if user:
        if user["google_sub"] and user["google_sub"] != claims["sub"]:
            raise HTTPException(status_code=409, detail="This email is linked to a different Google account.")
        with connection() as conn:
            conn.execute(
                "UPDATE users SET google_sub = ? WHERE id = ?",
                (claims["sub"], user["id"]),
            )
        user = fetch_one("SELECT id, name, email FROM users WHERE id = ?", (user["id"],))
    else:
        user_id = str(uuid.uuid4())
        name = (claims.get("name") or email.split("@", 1)[0]).strip()[:80] or email
        with connection() as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, google_sub) VALUES (?, ?, ?, ?)",
                (user_id, name, email, claims["sub"]),
            )
        user = fetch_one("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    return _session_response(user)


@router.get("/me")
async def current_account(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: dict = Depends(get_current_user),
):
    if credentials:
        import hashlib

        token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        with connection() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
    return {"status": "signed_out"}
