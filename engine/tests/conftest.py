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
TEST_EMAIL_DOMAIN = "tests.example"


def cleanup_test_data() -> None:
    """Remove everything the DB tests created so the shared dev database stays clean.

    Runs as the database owner with triggers suspended (session_replication_role = replica): that is
    the only way past the immutability guards, and it touches only rows created by tests.
    """
    import psycopg

    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres", autocommit=True) as conn:
        conn.execute("set session_replication_role = replica")
        users = [r[0] for r in conn.execute(
            "select id from auth.users where email like %s", (f"%@{TEST_EMAIL_DOMAIN}",)).fetchall()]
        companies = [r[0] for r in conn.execute(
            "select id from public.companies where legal_name like 'Test a %' or legal_name like 'Test b %'").fetchall()]
        if companies:
            for table in ("emission_calculations", "file_reviews", "bill_extractions", "validation_issues", "categorizations",
                          "activity_records", "uploaded_files", "tasks", "notes", "project_categories", "denominators",
                          "wq_samples", "labour_monthly", "incidents"):
                conn.execute(f"delete from public.{table} where company_id = any(%s)", (companies,))
            conn.execute("update public.projects set current_version_id = null where company_id = any(%s)", (companies,))
            conn.execute("delete from public.calculation_versions where company_id = any(%s)", (companies,))
            conn.execute("delete from public.projects where company_id = any(%s)", (companies,))
            conn.execute("delete from public.memberships where company_id = any(%s)", (companies,))
            conn.execute("delete from public.facilities where company_id = any(%s)", (companies,))
            conn.execute("delete from public.companies where id = any(%s)", (companies,))
        # Reference/library fixtures (test-only names and sources)
        conn.execute("delete from public.wq_samples where parameter_key like 'testparam_%'")
        conn.execute("delete from ref.wq_thresholds where regulator = 'TEST'")
        conn.execute("delete from ref.wq_parameters where key like 'testparam_%'")
        conn.execute("delete from lib.factor_conversions where emission_factor_id in "
                     "(select id from lib.emission_factors where source_name like 'Test fixture%')")
        conn.execute("delete from lib.emission_factors where source_name like 'Test fixture%'")
        if users:
            conn.execute("delete from public.internal_users where user_id = any(%s)", (users,))
            conn.execute("delete from public.memberships where user_id = any(%s)", (users,))
            conn.execute("delete from public.profiles where user_id = any(%s)", (users,))
            conn.execute("delete from auth.identities where user_id = any(%s)", (users,))
            conn.execute("delete from auth.users where id = any(%s)", (users,))


@pytest.fixture(scope="session", autouse=True)
def _clean_shared_db(request):
    """Clean up before (leftovers from an aborted run) and after the DB test session."""
    if not any(item.get_closest_marker("db") for item in request.session.items):
        yield
        return
    cleanup_test_data()
    yield
    cleanup_test_data()


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
            email = f"{role.lower()}.{tag}.{suffix}@{TEST_EMAIL_DOMAIN}"
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

    email = f"internal.{role.lower()}.{uuid.uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
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
