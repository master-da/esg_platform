"""Server-side calls to Supabase Auth-admin and Storage using the secret key.

The secret key lives only in the engine environment; it is never returned to clients.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.db import Tx


def _headers(content_type: str | None = "application/json") -> dict[str, str]:
    key = get_settings().supabase_secret_key
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _url(path: str) -> str:
    return f"{get_settings().supabase_url}{path}"


def invite_user(tx: Tx, email: str, full_name: str | None) -> tuple[str, bool]:
    """Invite by email. Returns (user_id, invitation_sent). Existing users are reused."""
    email = email.strip().lower()
    existing = tx.scalar("select user_id from public.profiles where lower(email) = %s", (email,))
    if existing:
        return str(existing), False
    resp = httpx.post(
        _url("/auth/v1/invite"),
        headers=_headers(),
        json={"email": email, "data": {"full_name": full_name} if full_name else {}},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise HTTPException(502, f"Could not send invitation: {resp.text}")
    return resp.json()["id"], True


def create_user(email: str, password: str, full_name: str | None = None) -> str:
    """Create a confirmed user directly (dev bootstrap and tests only)."""
    resp = httpx.post(
        _url("/auth/v1/admin/users"),
        headers=_headers(),
        json={"email": email, "password": password, "email_confirm": True,
              "user_metadata": {"full_name": full_name} if full_name else {}},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"create_user failed: {resp.status_code} {resp.text}")
    return resp.json()["id"]


# -- Storage -------------------------------------------------------------------------

def storage_upload(path: str, data: bytes, content_type: str) -> None:
    bucket = get_settings().storage_bucket
    resp = httpx.post(
        _url(f"/storage/v1/object/{bucket}/{path}"),
        headers={**_headers(content_type), "x-upsert": "false"},
        content=data,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise HTTPException(502, f"Storage upload failed: {resp.text}")


def storage_download(path: str) -> bytes:
    bucket = get_settings().storage_bucket
    resp = httpx.get(_url(f"/storage/v1/object/{bucket}/{path}"), headers=_headers(None), timeout=60)
    if resp.status_code >= 400:
        raise HTTPException(502, f"Storage download failed: {resp.text}")
    return resp.content


def storage_signed_url(path: str, expires_in: int = 300, download_name: str | None = None) -> str:
    bucket = get_settings().storage_bucket
    resp = httpx.post(
        _url(f"/storage/v1/object/sign/{bucket}/{path}"),
        headers=_headers(),
        json={"expiresIn": expires_in},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise HTTPException(502, f"Could not sign URL: {resp.text}")
    signed = resp.json()["signedURL"]
    url = f"{get_settings().supabase_url}/storage/v1{signed}"
    if download_name:
        url += ("&" if "?" in url else "?") + "download=" + quote(download_name)
    return url
