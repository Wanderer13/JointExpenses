"""Verify Google Identity Services ID tokens."""

from __future__ import annotations

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleAuthError(Exception):
    pass


def verify_google_id_token(credential: str, client_id: str) -> dict:
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except Exception as exc:  # noqa: BLE001 — google-auth raises varied errors
        raise GoogleAuthError("Invalid Google credential") from exc

    iss = idinfo.get("iss")
    if iss not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleAuthError("Invalid Google token issuer")
    if not idinfo.get("email_verified"):
        raise GoogleAuthError("Google email is not verified")
    if not idinfo.get("sub") or not idinfo.get("email"):
        raise GoogleAuthError("Google token missing required claims")
    return idinfo
