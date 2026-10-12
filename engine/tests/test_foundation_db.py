"""Feature 1, 2, 18 acceptance criteria: tenancy, roles, audit log, catalog safety."""

from __future__ import annotations

import psycopg
import pytest

from tests.conftest import Rest, bearer

pytestmark = pytest.mark.db

# Tables in `public` that legitimately have no company_id (identity, not business data).
NO_COMPANY_ID = {"profiles", "internal_users"}


# -- Tenant isolation (F1, F2, F18) ------------------------------------------------------


def test_company_a_cannot_read_company_b(tenant_a, tenant_b):
    for role, token in tenant_a.tokens.items():
        rest = Rest(token)
        assert rest.get("companies", id=f"eq.{tenant_b.company_id}").json() == [], role
        assert rest.get("facilities", company_id=f"eq.{tenant_b.company_id}").json() == [], role
        assert rest.get("memberships", company_id=f"eq.{tenant_b.company_id}").json() == [], role
        own = rest.get("companies", select="id").json()
        assert [c["id"] for c in own] == [tenant_a.company_id], role


def test_company_a_cannot_write_company_b(tenant_a, tenant_b):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    r = rest.patch("companies", {"legal_name": "hijacked"}, id=f"eq.{tenant_b.company_id}")
    assert r.status_code in (200, 204) and r.json() == []  # RLS: zero rows affected
    r = rest.post("facilities", {"company_id": tenant_b.company_id, "name": "Intruder"})
    assert r.status_code in (401, 403)
    r = rest.delete("facilities", id=f"eq.{tenant_b.facility_id}")
    assert r.json() == []


def test_engine_rejects_cross_tenant_actions(engine, tenant_a, tenant_b):
    r = engine.post(
        f"/companies/{tenant_b.company_id}/invitations",
        headers=bearer(tenant_a.tokens["COMPANY_ADMIN"]),
        json={"email": "someone@tests.example", "role": "VIEWER"},
    )
    assert r.status_code == 403


def test_anonymous_has_no_access():
    rest = Rest(None)
    for table in ("companies", "facilities", "memberships", "audit_log", "profiles"):
        r = rest.get(table)
        assert r.status_code in (401, 403), table


# -- Roles (F2) ----------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["VIEWER", "AUDITOR"])
def test_read_only_roles_cannot_write(tenant_a, role):
    rest = Rest(tenant_a.tokens[role])
    assert rest.patch("companies", {"legal_name": "x"}, id=f"eq.{tenant_a.company_id}").json() == []
    assert rest.post("facilities", {"company_id": tenant_a.company_id, "name": f"x-{role}"}).status_code in (401, 403)
    assert rest.patch("facilities", {"name": "x"}, id=f"eq.{tenant_a.facility_id}").json() == []
    assert rest.delete("facilities", id=f"eq.{tenant_a.facility_id}").json() == []


def test_company_admin_can_edit_profile_and_add_facility(tenant_a):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    r = rest.patch("companies", {"city": "Gazipur"}, id=f"eq.{tenant_a.company_id}")
    assert r.status_code == 200 and r.json()[0]["city"] == "Gazipur"
    r = rest.post(
        "facilities", {"company_id": tenant_a.company_id, "name": "Second plant", "facility_type": "WAREHOUSE"}
    )
    assert r.status_code == 201


def test_company_admin_cannot_change_org_metadata(tenant_a):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    r = rest.patch("companies", {"license_tier": "TIER_TBD"}, id=f"eq.{tenant_a.company_id}")
    assert r.status_code in (401, 403)  # column-level privilege


def test_only_company_admin_invites(engine, tenant_a):
    for role in ("SUSTAINABILITY_MANAGER", "DATA_ENTRY", "VIEWER", "AUDITOR"):
        r = engine.post(
            f"/companies/{tenant_a.company_id}/invitations",
            headers=bearer(tenant_a.tokens[role]),
            json={"email": "nobody@tests.example", "role": "VIEWER"},
        )
        assert r.status_code == 403, role


def test_company_level_facility_is_protected(tenant_a):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    r = rest.delete("facilities", id=f"eq.{tenant_a.company_level_facility_id}")
    assert r.json() == []


# -- Privilege escalation ------------------------------------------------------------------


def test_user_cannot_make_themselves_internal(tenant_a):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    me = rest.rpc("my_context").json()
    r = rest.post("internal_users", {"user_id": me["user_id"], "internal_role": "PLATFORM_ADMIN"})
    assert r.status_code in (401, 403)


def test_user_cannot_change_own_membership_role(tenant_a):
    rest = Rest(tenant_a.tokens["VIEWER"])
    r = rest.patch("memberships", {"role": "COMPANY_ADMIN"}, company_id=f"eq.{tenant_a.company_id}")
    assert r.status_code in (401, 403)


# -- Audit log (F18) -----------------------------------------------------------------------


def test_audit_log_hidden_from_every_external_role(tenant_a):
    for role, token in tenant_a.tokens.items():
        assert Rest(token).get("audit_log", limit=5).json() == [], role


def test_audit_log_visible_to_internal(internal_user, tenant_a):
    rows = Rest(internal_user).get("audit_log", company_id=f"eq.{tenant_a.company_id}", limit=5).json()
    assert rows, "internal users should see audit entries"


def test_changes_are_audited_with_actor(tenant_a, superuser_conn):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    rest.patch("companies", {"district": "Dhaka"}, id=f"eq.{tenant_a.company_id}")
    row = superuser_conn.execute(
        "select actor_user_id, old_value->>'district' as old, new_value->>'district' as new "
        "from public.audit_log where entity = 'public.companies' and entity_id = %s and action = 'UPDATE' "
        "order by id desc limit 1",
        (tenant_a.company_id,),
    ).fetchone()
    assert row["actor_user_id"] is not None and row["new"] == "Dhaka"


def test_audit_log_is_immutable_even_for_owner(superuser_conn):
    with pytest.raises(psycopg.errors.RaiseException):
        superuser_conn.execute(
            "update public.audit_log set action = 'X' where id = (select min(id) from public.audit_log)"
        )
    with pytest.raises(psycopg.errors.RaiseException):
        superuser_conn.execute("delete from public.audit_log where id = (select min(id) from public.audit_log)")
    with pytest.raises(psycopg.errors.RaiseException):
        superuser_conn.execute("truncate public.audit_log")


# -- Catalog checks (F18: every business row carries company_id; RLS everywhere) -------------


def test_every_public_table_has_company_id_and_rls(superuser_conn):
    tables = superuser_conn.execute(
        """select c.relname, c.relrowsecurity,
                  exists(select 1 from information_schema.columns col
                         where col.table_schema = 'public' and col.table_name = c.relname
                           and col.column_name = 'company_id') as has_company_id
           from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind = 'r'"""
    ).fetchall()
    assert tables
    for t in tables:
        assert t["relrowsecurity"], f"RLS disabled on public.{t['relname']}"
        if t["relname"] not in NO_COMPANY_ID:
            assert t["has_company_id"], f"public.{t['relname']} has no company_id"


def test_anon_has_no_table_privileges(superuser_conn):
    rows = superuser_conn.execute(
        """select table_schema, table_name, privilege_type from information_schema.role_table_grants
           where grantee = 'anon' and table_schema in ('public', 'ref', 'lib')"""
    ).fetchall()
    assert rows == []


def test_lib_schema_not_granted_to_clients(superuser_conn):
    rows = superuser_conn.execute(
        """select table_name from information_schema.role_table_grants
           where grantee in ('authenticated', 'anon') and table_schema = 'lib'"""
    ).fetchall()
    assert rows == []
    row = superuser_conn.execute("select has_schema_privilege('authenticated', 'lib', 'usage') as u").fetchone()
    assert not row["u"]


def test_authenticated_cannot_write_reference_data(tenant_a):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    r = rest.post(
        "countries",
        {"code": "XX", "name": "Nowhere", "default_currency": "BDT", "default_timezone": "UTC"},
        schema="ref",
    )
    assert r.status_code in (401, 403)
