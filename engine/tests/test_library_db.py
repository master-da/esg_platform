"""Emission Factor Library (PRD Feature 6): access control, factor lifecycle, code confidentiality."""

from __future__ import annotations

import random

import httpx
import pytest

from app.config import get_settings
from tests.conftest import Rest, bearer

pytestmark = pytest.mark.db


def _leaf(engine, token, path_suffix: str) -> dict:
    nodes = engine.get("/library/tree", headers=bearer(token)).json()
    return next(n for n in nodes if n["path"].endswith(path_suffix))


# A far-future year unique to this run keeps test factors from overlapping earlier runs' factors.
YEAR = random.randint(2200, 9000)


def _draft(**over) -> dict:
    body = {"geography_code": "BD", "activity_unit": "L", "co2e": "2.5", "gwp_version": "AR5",
            "source_name": "Test fixture (not a real factor)", "source_year": YEAR,
            "valid_from": f"{YEAR}-01-01", "valid_to": f"{YEAR}-12-31"}
    body.update(over)
    return body


def test_external_users_cannot_open_the_library(engine, tenant_a):
    for role in ("COMPANY_ADMIN", "SUSTAINABILITY_MANAGER", "AUDITOR"):
        assert engine.get("/library/tree", headers=bearer(tenant_a.tokens[role])).status_code == 403


def test_internal_users_can_view_but_only_editors_can_change(engine, internal_user, platform_admin):
    leaf = _leaf(engine, internal_user, "s1.stationary.nonrenewable.liquid.diesel")
    assert leaf["code"] == "01010000001202"
    detail = engine.get(f"/library/nodes/{leaf['id']}", headers=bearer(internal_user)).json()
    assert detail["factors"] and all(f["source_name"] for f in detail["factors"])
    r = engine.post("/library/factors", headers=bearer(internal_user), json=_draft(taxonomy_node_id=leaf["id"]))
    assert r.status_code == 403


def test_factor_lifecycle_and_overlap_resolution(engine, platform_admin):
    leaf = _leaf(engine, platform_admin, "s1.stationary.nonrenewable.liquid.kerosene")
    h = bearer(platform_admin)
    a = engine.post("/library/factors", headers=h, json=_draft(taxonomy_node_id=leaf["id"])).json()
    assert engine.post(f"/library/factors/{a['id']}/activate", headers=h).status_code == 200

    # A second factor overlapping the same node/geography/period cannot also be active.
    b = engine.post("/library/factors", headers=h, json=_draft(taxonomy_node_id=leaf["id"], co2e="2.6",
                                                               valid_from=f"{YEAR}-06-01")).json()
    r = engine.post(f"/library/factors/{b['id']}/activate", headers=h)
    assert r.status_code == 409 and "overlaps" in r.json()["detail"]

    # Explicit resolution: retire the first, then the second can be activated.
    assert engine.post(f"/library/factors/{a['id']}/retire", headers=h).status_code == 200
    assert engine.post(f"/library/factors/{b['id']}/activate", headers=h).status_code == 200

    # Active factors are immutable; corrections go through a new version.
    assert engine.patch(f"/library/factors/{b['id']}", headers=h,
                        json=_draft(taxonomy_node_id=leaf["id"])).status_code == 409
    nv = engine.post(f"/library/factors/{b['id']}/new-version", headers=h)
    assert nv.status_code == 201 and nv.json()["version"] == b["version"] + 1
    engine.delete(f"/library/factors/{nv.json()['id']}", headers=h)
    engine.post(f"/library/factors/{b['id']}/retire", headers=h)


def test_factor_requires_source_unit_geography_and_validity(engine, platform_admin):
    leaf = _leaf(engine, platform_admin, "s1.stationary.nonrenewable.liquid.kerosene")
    for missing in ("source_name", "activity_unit", "geography_code", "valid_from", "valid_to"):
        body = _draft(taxonomy_node_id=leaf["id"])
        body.pop(missing)
        assert engine.post("/library/factors", headers=bearer(platform_admin), json=body).status_code == 422, missing


def test_factor_codes_are_not_exposed_to_clients(tenant_a):
    s = get_settings()
    spec = httpx.get(f"{s.supabase_url}/rest/v1/", headers={"apikey": s.supabase_publishable_key,
                                                            "Authorization": f"Bearer {tenant_a.tokens['VIEWER']}",
                                                            "Accept-Profile": "ref"}, timeout=20).text
    assert "factor_code" not in spec
    assert '"code"' not in Rest(tenant_a.tokens["VIEWER"]).get("taxonomy_labels", schema="ref", limit=1).text
    labels = Rest(tenant_a.tokens["VIEWER"]).get("taxonomy_labels", schema="ref",
                                                 path="eq.s1.stationary.nonrenewable.liquid.petrol").json()
    assert labels[0]["display_path"] == "Scope 1 > Stationary combustion > Non-renewable fuels > Liquid > Petrol"
