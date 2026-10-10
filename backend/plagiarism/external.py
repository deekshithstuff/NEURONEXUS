"""Optional external plagiarism provider integration.

PaperPilot can delegate comparison to an external service (currently a
Copyleaks-compatible endpoint) when an operator configures credentials through
environment variables. Credentials are only ever read on the backend and are
never returned to the frontend. If the provider is not configured, cannot be
reached, or returns malformed data, the scan fails with an explicit error and
no matches are invented.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from typing import Any, Callable

SUPPORTED_PROVIDERS = ("copyleaks",)
DEFAULT_BASE_URL = "https://api.copyleaks.com"
DEFAULT_LOGIN_URL = "https://id.copyleaks.com"


class ExternalScanError(RuntimeError):
    """Raised when an external plagiarism scan cannot be completed honestly."""


def _provider_name() -> str:
    return os.getenv("PAPERPILOT_PLAGIARISM_PROVIDER", "").strip().lower()


def external_status() -> dict[str, Any]:
    provider = _provider_name()
    configured = (
        provider == "copyleaks"
        and bool(os.getenv("COPYLEAKS_EMAIL"))
        and bool(os.getenv("COPYLEAKS_API_KEY"))
    )
    return {
        "provider": provider or None,
        "configured": configured,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "requires_consent": True,
        "base_url": os.getenv("COPYLEAKS_BASE_URL", DEFAULT_BASE_URL) if configured else None,
        "message": (
            "An external comparison provider is configured; documents are sent only after explicit consent."
            if configured
            else "No external provider configured. Only the internal corpus comparison is available."
        ),
    }


def fetch_external_report(
    text: str,
    *,
    title: str | None = None,
    http: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    provider = _provider_name()
    if provider not in SUPPORTED_PROVIDERS:
        raise ExternalScanError("No supported external plagiarism provider is configured.")
    if not (os.getenv("COPYLEAKS_EMAIL") and os.getenv("COPYLEAKS_API_KEY")):
        raise ExternalScanError("External provider credentials are not configured.")
    if not text.strip():
        raise ExternalScanError("There is no extractable text to send to the external provider.")

    base_url = os.getenv("COPYLEAKS_BASE_URL", DEFAULT_BASE_URL)
    login_url = os.getenv("COPYLEAKS_LOGIN_URL", DEFAULT_LOGIN_URL)
    client = http() if http else _default_client()
    try:
        token = _login(client, login_url, os.environ["COPYLEAKS_EMAIL"], os.environ["COPYLEAKS_API_KEY"])
        scan_id = f"pp-{uuid.uuid4().hex[:12]}"
        _submit(client, base_url, token, scan_id, text, title)
        raw = _poll(client, base_url, token, scan_id)
    except ExternalScanError:
        raise
    except Exception as exc:  # pragma: no cover - network dependent
        raise ExternalScanError(f"The external provider request failed: {exc}") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return _normalize_result(raw, provider)


def _default_client():
    import httpx

    return httpx.Client(timeout=30.0)


def _login(client: Any, login_url: str, email: str, api_key: str) -> str:
    response = client.post(f"{login_url}/v3/account/login/api", json={"email": email, "key": api_key})
    if response.status_code >= 400:
        raise ExternalScanError(f"External provider authentication failed with status {response.status_code}.")
    token = (response.json() or {}).get("access_token")
    if not token:
        raise ExternalScanError("External provider authentication did not return an access token.")
    return token


def _submit(client: Any, base_url: str, token: str, scan_id: str, text: str, title: str | None) -> None:
    payload = {
        "base64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "filename": f"{(title or 'manuscript')[:60]}.txt",
    }
    response = client.post(
        f"{base_url}/v3/scans/submit/file/{scan_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code >= 400:
        raise ExternalScanError(f"External provider rejected the submission with status {response.status_code}.")


def _poll(client: Any, base_url: str, token: str, scan_id: str, attempts: int = 20, interval: float = 3.0) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(attempts):
        response = client.get(f"{base_url}/v3/scans/{scan_id}/result", headers=headers)
        if response.status_code == 200:
            payload = response.json()
            if payload.get("status") in {"completed", "finished", None}:
                return payload
        elif response.status_code not in {202, 404}:
            raise ExternalScanError(f"External provider polling failed with status {response.status_code}.")
        time.sleep(interval)
    raise ExternalScanError("The external provider did not finish scanning before the timeout.")


def _normalize_result(raw: dict[str, Any], provider: str) -> dict[str, Any]:
    results = raw.get("results") or raw.get("items") or []
    if not isinstance(results, list):
        raise ExternalScanError("The external provider returned an unexpected result format.")
    matches: list[dict[str, Any]] = []
    for index, entry in enumerate(results, start=1):
        if not isinstance(entry, dict):
            continue
        source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
        matches.append(
            {
                "passage": str(entry.get("matchedText") or entry.get("text") or ""),
                "location": {
                    "paragraph_index": None,
                    "paragraph_number": None,
                    "sentence_index": None,
                    "section_heading": "",
                    "section_type": "other",
                    "char_start": None,
                    "char_end": None,
                },
                "source": {
                    "id": str(source.get("id") or f"{provider}-{index}"),
                    "title": str(source.get("title") or "External source"),
                    "url": source.get("url"),
                    "source_type": "external",
                    "authors": [],
                    "year": None,
                },
                "method": "external",
                "similarity": float(entry.get("score") or entry.get("similarity") or 0.0),
                "coverage": None,
                "matched_words": int(entry.get("matchedWords") or 0),
                "attributed": False,
                "quoted": False,
                "classification": "external_match",
                "matched_text": str(entry.get("sourceText") or ""),
                "note": f"Reported by the external comparison provider '{provider}'. Verify against the original source.",
            }
        )
    return {
        "provider": f"external:{provider}",
        "matches": matches,
        "external_summary": {
            "scanned_words": raw.get("scannedWords"),
            "plagiarism_score": raw.get("plagiarismScore"),
            "result_count": len(matches),
        },
    }
