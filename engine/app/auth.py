"""Supabase JWT verification and request-scoped user context."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings
from app.db import Tx, transaction

ASYMMETRIC_ALGS = ["ES256", "RS256", "EdDSA"]


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True)


def verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise jwt.InvalidTokenError("HS256 tokens are not accepted")
            key: Any = settings.supabase_jwt_secret
        elif alg in ASYMMETRIC_ALGS:
            key = _jwks_client().get_signing_key_from_jwt(token).key
        else:
            raise jwt.InvalidTokenError(f"Unsupported alg {alg}")
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
    if claims.get("role") != "authenticated":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token is not a user session")
    return claims


@dataclass
class User:
    id: str
    email: str | None
    claims: dict[str, Any]


def current_user(authorization: str = Header(default="")) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = verify_token(authorization.split(" ", 1)[1].strip())
    return User(id=claims["sub"], email=claims.get("email"), claims=claims)


def user_tx(user: User = Depends(current_user)) -> Iterator[Tx]:
    """One transaction per request, acting as the verified user (RLS applies)."""
    with transaction(user.claims) as tx:
        yield tx


# -- authorisation helpers (evaluated in the database, same functions RLS uses) ---------

def _check(tx: Tx, expr: str, *params: Any, message: str) -> None:
    if not tx.scalar(f"select {expr}", params):
        raise HTTPException(status.HTTP_403_FORBIDDEN, message)


def require_internal(tx: Tx) -> None:
    _check(tx, "app.is_internal()", message="Internal users only")


def require_platform_admin(tx: Tx) -> None:
    _check(tx, "app.is_platform_admin()", message="Platform admins only")


def require_library_editor(tx: Tx) -> None:
    _check(tx, "app.can_edit_library()", message="Only authorised library editors can change the library")


def require_read(tx: Tx, company_id: str) -> None:
    _check(tx, "app.can_read(%s)", company_id, message="No access to this company")


def require_write(tx: Tx, company_id: str) -> None:
    _check(tx, "app.can_write(%s)", company_id, message="Your role is read-only for this company")


def require_manage(tx: Tx, company_id: str) -> None:
    _check(tx, "app.can_manage(%s)", company_id, message="Only company admins or sustainability managers can do this")


def require_approve(tx: Tx, company_id: str) -> None:
    _check(tx, "app.can_approve(%s)", company_id, message="Your role cannot approve or lock projects")


def require_user_admin(tx: Tx, company_id: str) -> None:
    _check(tx, "app.can_admin_users(%s)", company_id, message="Only company admins can manage users")
