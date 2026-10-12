"""Shared fixtures.

Tests marked `db` need the local Supabase stack (`make up`). They create their own tenants
with unique emails, so they never depend on (or disturb) the dev bootstrap data.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import pytest

from app.config import get_settings

ROLES = ["COMPANY_ADMIN", "SUSTAINABILITY_MANAGER", "FACILITY_MANAGER", "DATA_ENTRY", "AUDITOR", "VIEWER"]
PASSWORD = "Test-Password-123!"


def login(email: str, password: str = PASSWORD) -> str:
    s = get_settings()
    r = httpx.post(
        f"{s.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": s.supabase_publishable_key},
        json={"email": email, "password": password},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


class Rest:
    """Minimal PostgREST client acting as a given user (exactly what the browser can do)."""

    def __init__(self, token: str | None):
        s = get_settings()
        self.base = f"{s.supabase_url}/rest/v1"
        self.headers = {"apikey": s.supabase_publishable_key, "Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _h(self, schema: str | None, extra: dict | None = None) -> dict:
        h = dict(self.headers)
        if schema:
            h["Accept-Profile"] = schema
            h["Content-Profile"] = schema
        h.update(extra or {})
        return h

    def get(self, resource: str, schema: str | None = None, **params) -> httpx.Response:
        return httpx.get(f"{self.base}/{resource}", headers=self._h(schema), params=params, timeout=20)

    def post(self, resource: str, body, schema: str | None = None) -> httpx.Response:
        return httpx.post(
            f"{self.base}/{resource}",
            headers=self._h(schema, {"Prefer": "return=representation"}),
            json=body,
            timeout=20,
        )

    def patch(self, resource: str, body, schema: str | None = None, **params) -> httpx.Response:
        return httpx.patch(
            f"{self.base}/{resource}",
            headers=self._h(schema, {"Prefer": "return=representation"}),
            params=params,
            json=body,
            timeout=20,
        )

    def delete(self, resource: str, schema: str | None = None, **params) -> httpx.Response:
        return httpx.delete(
            f"{self.base}/{resource}",
            headers=self._h(schema, {"Prefer": "return=representation"}),
            params=params,
            timeout=20,
        )

    def rpc(self, fn: str, body: dict | None = None) -> httpx.Response:
        return httpx.post(f"{self.base}/rpc/{fn}", headers=self._h(None), json=body or {}, timeout=20)


@dataclass
class Tenant:
    company_id: str
    facility_id: str
    company_level_facility_id: str
    tokens: dict[str, str] = field(default_factory=dict)  # role -> token
    emails: dict[str, str] = field(default_factory=dict)


def _create_tenant(tag: str) -> Tenant:
    from app.db import transaction
    from app.supabase_admin import create_user

    suffix = uuid.uuid4().hex[:8]
    with transaction(None) as tx:
        tx.execute("select set_config('app.source', 'test', true)")
        company_id = str(
            tx.scalar(
                "insert into public.companies (legal_name, crm_record_id) values (%s, 'TEST') returning id",
                (f"Test {tag} {suffix}",),
            )
        )
        facility_id = str(
            tx.scalar(
                "insert into public.facilities (company_id, name, facility_type) values (%s, 'Plant 1', 'MANUFACTURING') "
                "returning id",
                (company_id,),
            )
        )
        cl = str(
            tx.scalar("select id from public.facilities where company_id = %s and is_company_level", (company_id,))
        )
        tenant = Tenant(company_id, facility_id, cl)
        for role in ROLES:
            email = f"{role.lower()}.{tag}.{suffix}@tests.example"
            uid = create_user(email, PASSWORD)
            tx.execute(
                "insert into public.memberships (company_id, user_id, role, status) values (%s, %s, %s, 'active')",
                (company_id, uid, role),
            )
            tenant.emails[role] = email
    for role, email in tenant.emails.items():
        tenant.tokens[role] = login(email)
    return tenant


def _create_internal(role: str, can_edit_library: bool) -> tuple[str, str]:
    from app.db import transaction
    from app.supabase_admin import create_user

    email = f"internal.{role.lower()}.{uuid.uuid4().hex[:8]}@tests.example"
    uid = create_user(email, PASSWORD)
    with transaction(None) as tx:
        tx.execute(
            "insert into public.internal_users (user_id, internal_role, can_edit_library) values (%s, %s, %s)",
            (uid, role, can_edit_library),
        )
    return uid, login(email)


@pytest.fixture(scope="session")
def tenant_a() -> Tenant:
    return _create_tenant("a")


@pytest.fixture(scope="session")
def tenant_b() -> Tenant:
    return _create_tenant("b")


@pytest.fixture(scope="session")
def platform_admin() -> str:
    return _create_internal("PLATFORM_ADMIN", True)[1]


@pytest.fixture(scope="session")
def internal_user() -> str:
    return _create_internal("INTERNAL_USER", False)[1]


@pytest.fixture(scope="session")
def engine() -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def superuser_conn():
    """Direct connection as the database owner, for checks no app role may perform."""
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres", row_factory=dict_row, autocommit=True
    )
    yield conn
    conn.close()
