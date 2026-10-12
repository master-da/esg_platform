"""Acceptance criteria for the environment & people modules (PRD Features 8-13)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import psycopg
import pytest

from tests.conftest import Rest, bearer

pytestmark = pytest.mark.db


def D(x) -> Decimal:
    return Decimal(str(x))


@pytest.fixture(scope="module")
def proj(engine, tenant_a):
    h = bearer(tenant_a.tokens["SUSTAINABILITY_MANAGER"])
    r = engine.post(
        "/projects",
        headers=h,
        json={
            "company_id": tenant_a.company_id,
            "name": "Modules",
            "period_type": "quarter",
            "boundary": "division",
            "division_name": f"modules-{uuid.uuid4().hex[:6]}",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def manual(engine, token, pid, key, **values):
    r = engine.post(f"/projects/{pid}/terminals/{key}/manual", headers=bearer(token), json={"values": values})
    assert r.status_code == 201, r.text
    return r.json()["file_id"]


# -- F8 Energy -----------------------------------------------------------------------------


def test_energy_total_renewable_share_and_switchable_intensity(engine, tenant_a, proj):
    tok = tenant_a.tokens["DATA_ENTRY"]
    for m, end in ((1, 31), (2, 28), (3, 31)):
        manual(
            engine,
            tok,
            proj,
            "s2_electricity",
            facility="Plant 1",
            period_start=f"2025-0{m}-01",
            period_end=f"2025-0{m}-{end}",
            supplier_name="DESCO",
            electricity_type="Grid electricity",
            quantity=1000,
            unit="kWh",
            data_basis="Utility bill / meter reading",
        )
    manual(
        engine,
        tok,
        proj,
        "energy_renewable",
        facility="Plant 1",
        period_start="2025-01-01",
        period_end="2025-03-31",
        source="Solar PV",
        quantity=600,
        unit="kWh",
        data_basis="Metered / invoice",
    )
    # Diesel in a generator: converted to kWh with the matched DESNZ factor's own net-CV conversion.
    manual(
        engine,
        tok,
        proj,
        "s1_stationary",
        facility="Plant 1",
        period_start="2025-01-01",
        period_end="2025-03-31",
        equipment_type="Generator",
        fuel_type="Diesel",
        quantity=100,
        unit="L",
        data_basis="Metered / invoice",
    )
    cat = engine.get(f"/projects/{proj}/terminals/s1_stationary/categorizations", headers=bearer(tok)).json()[0]
    engine.post(f"/categorizations/{cat['id']}/accept", headers=bearer(tok), json={})

    e = engine.get(f"/projects/{proj}/energy", headers=bearer(tok)).json()
    diesel_kwh = D(100) * D("2.66155") / D("0.26808")  # litres x (kg/L) / (kg/kWh) = kWh, DESNZ 2025 net CV
    assert D(e["by_source_kwh"]["electricity"]) == 3000
    assert D(e["by_source_kwh"]["renewable"]) == 600
    assert abs(D(e["by_source_kwh"]["fuels_stationary"]) - diesel_kwh) < D("0.0001")
    assert abs(D(e["total_kwh"]) - (3600 + diesel_kwh)) < D("0.0001")
    assert abs(D(e["renewable_share_pct"]) - 600 * 100 / (3600 + diesel_kwh)) < D("0.0001")
    assert e["unconverted"] == []
    assert e["by_source_kwh"]["fuels_mobile"] is None, "a source with no data is Missing, not 0"

    # Intensity: changing the production denominator recalculates without new data entry.
    rest = Rest(tenant_a.tokens["SUSTAINABILITY_MANAGER"])
    company = tenant_a.company_id
    r = rest.post(
        "denominators", {"company_id": company, "project_id": proj, "kind": "production_mass", "value": 10, "unit": "t"}
    )
    assert r.status_code == 201, r.text
    i1 = engine.get(f"/projects/{proj}/energy?denominator=production_mass", headers=bearer(tok)).json()["intensity"]
    rest.patch("denominators", {"value": 20}, id=f"eq.{r.json()[0]['id']}")
    i2 = engine.get(f"/projects/{proj}/energy?denominator=production_mass", headers=bearer(tok)).json()["intensity"]
    assert abs(D(i1["value"]) - 2 * D(i2["value"])) < D("0.000001")
    none = engine.get(f"/projects/{proj}/energy?denominator=revenue", headers=bearer(tok)).json()["intensity"]
    assert none["value"] is None, "no revenue denominator -> intensity is Missing"


# -- F9 Water ------------------------------------------------------------------------------


def test_water_log_records_and_missing_months(engine, tenant_a, proj):
    tok = tenant_a.tokens["DATA_ENTRY"]
    manual(
        engine,
        tok,
        proj,
        "water_withdrawal",
        facility="Plant 1",
        period_start="2025-01-01",
        period_end="2025-01-31",
        source="Groundwater",
        quantity=5000,
        unit="m3",
        data_basis="Metered / invoice",
    )
    manual(
        engine,
        tok,
        proj,
        "water_withdrawal",
        facility="Plant 1",
        period_start="2025-03-01",
        period_end="2025-03-31",
        source="Groundwater",
        quantity=4000,
        unit="m3",
        data_basis="Metered / invoice",
    )
    manual(
        engine,
        tok,
        proj,
        "water_discharge",
        facility="Plant 1",
        period_start="2025-01-01",
        period_end="2025-01-31",
        destination="Surface water (river/canal)",
        treatment="Treated in own ETP",
        quantity=3500,
        unit="m3",
        data_basis="Metered / invoice",
    )
    w = engine.get(f"/projects/{proj}/water", headers=bearer(tok)).json()
    assert D(w["withdrawal_m3"]) == 9000 and D(w["discharge_m3"]) == 3500
    assert D(w["consumption_m3"]) == 1500, "consumption only where both are reported (January)"
    feb = next(m for m in w["monthly"] if m["month"] == "2025-02")
    assert feb["withdrawal"] is None and "withdrawal" in feb["missing"], "missing months are Missing, never 0"
    assert w["verification"]["pending"] == 0


# -- F10 Water quality / ETP -----------------------------------------------------------------


def test_wq_threshold_flags_pass_warning_fail_and_is_pure_data(tenant_a, superuser_conn):
    param = f"testparam_{uuid.uuid4().hex[:6]}"
    superuser_conn.execute("insert into ref.wq_parameters (key, name, unit) values (%s, 'Test COD', 'mg/L')", (param,))
    rest = Rest(tenant_a.tokens["FACILITY_MANAGER"])

    def sample(value):
        r = rest.post(
            "wq_samples",
            {
                "company_id": tenant_a.company_id,
                "facility_id": tenant_a.facility_id,
                "sample_date": "2025-02-10",
                "parameter_key": param,
                "value": value,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()[0]["result"]

    assert sample(50) == "NO_THRESHOLD"
    # A threshold is configuration data (no deployment). TEST FIXTURE: not a real regulatory limit.
    superuser_conn.execute(
        """insert into ref.wq_thresholds (parameter_key, max_value, warning_band_pct, regulator, regulation, source_url,
             valid_from) values (%s, 200, 10, 'TEST', 'Test fixture - not a regulation', 'https://example.invalid', '2020-01-01')""",
        (param,),
    )
    assert sample(150) == "PASS"
    assert sample(185) == "WARNING"
    assert sample(201) == "FAIL"


# -- F11 Waste -----------------------------------------------------------------------------


def test_waste_recycling_rate_and_hazardous_split(engine, tenant_a, proj):
    tok = tenant_a.tokens["DATA_ENTRY"]
    common = {
        "facility": "Plant 1",
        "period_start": "2025-01-01",
        "period_end": "2025-03-31",
        "supplier_name": "Green Waste Ltd",
        "unit": "t",
        "data_basis": "Weighbridge / manifest",
    }
    manual(
        engine,
        tok,
        proj,
        "s3_c05",
        waste_type="Commercial & industrial waste (mixed)",
        treatment="Landfill",
        hazardous="No",
        quantity=10,
        **common,
    )
    manual(
        engine,
        tok,
        proj,
        "s3_c05",
        waste_type="Paper & board",
        treatment="Recycling",
        hazardous="No",
        quantity=4,
        **common,
    )
    manual(
        engine,
        tok,
        proj,
        "s3_c05",
        waste_type="Chemical containers",
        treatment="Treatment",
        hazardous="Yes",
        quantity=1,
        **common,
    )
    w = engine.get(f"/projects/{proj}/waste", headers=bearer(tok)).json()
    assert D(w["total_t"]) == 15 and D(w["hazardous_t"]) == 1 and D(w["non_hazardous_t"]) == 14
    assert abs(D(w["recycling_rate_pct"]) - D(4) * 100 / 15) < D("0.0001")
    assert sum(1 for r in w["records"] if r["hazardous"]) == 1


# -- F12 Labour ----------------------------------------------------------------------------


def test_turnover_for_the_period_and_aggregate_only(tenant_a, engine):
    rest = Rest(tenant_a.tokens["COMPANY_ADMIN"])
    fac = tenant_a.facility_id
    for m, dep in (("2024-01-01", 2), ("2024-02-01", 3), ("2024-03-01", 1)):
        r = rest.post(
            "labour_monthly",
            {
                "company_id": tenant_a.company_id,
                "facility_id": fac,
                "month": m,
                "headcount_permanent": 90,
                "headcount_temporary": 10,
                "headcount_female": 60,
                "headcount_male": 40,
                "new_hires": 1,
                "departures": dep,
                "working_hours": 20000,
                "overtime_hours": 1000,
                "training_hours": 300,
            },
        )
        assert r.status_code == 201, r.text
    lab = engine.get(
        f"/companies/{tenant_a.company_id}/labour?start=2024-01-01&end=2024-03-31",
        headers=bearer(tenant_a.tokens["VIEWER"]),
    ).json()
    assert D(lab["turnover_rate_pct"]) == 6, "6 departures / average headcount 100"
    assert D(lab["training_hours_per_employee"]) == 9
    partial = engine.get(
        f"/companies/{tenant_a.company_id}/labour?start=2024-01-01&end=2024-04-30",
        headers=bearer(tenant_a.tokens["VIEWER"]),
    ).json()
    assert partial["turnover_rate_pct"] is None and partial["missing"], "a missing month makes turnover Missing"
    # Breakdowns must agree (aggregate integrity), and there is no column for any individual.
    bad = rest.post(
        "labour_monthly",
        {
            "company_id": tenant_a.company_id,
            "facility_id": fac,
            "month": "2024-05-01",
            "headcount_permanent": 10,
            "headcount_female": 3,
            "headcount_male": 3,
        },
    )
    assert bad.status_code >= 400


def test_labour_table_has_no_personal_fields(superuser_conn):
    cols = {
        r["column_name"]
        for r in superuser_conn.execute(
            "select column_name from information_schema.columns where table_name in ('labour_monthly', 'incidents')"
        )
    }
    assert not cols & {"employee_name", "name", "employee_id", "national_id", "email", "phone"}


# -- F13 Health & safety --------------------------------------------------------------------


def test_lost_time_incident_updates_ltifr(tenant_a, engine):
    rest = Rest(tenant_a.tokens["FACILITY_MANAGER"])
    q = f"/companies/{tenant_a.company_id}/safety?start=2024-01-01&end=2024-03-31"
    before = engine.get(q, headers=bearer(tenant_a.tokens["VIEWER"])).json()
    assert before["ltifr"] == 0 and D(before["hours_worked"]) == 63000
    r = rest.post(
        "incidents",
        {
            "company_id": tenant_a.company_id,
            "facility_id": tenant_a.facility_id,
            "occurred_on": "2024-02-14",
            "type": "injury",
            "severity": "moderate",
            "workers_affected": 1,
            "lost_time": True,
            "lost_days": 4,
            "root_cause": "Unguarded machine",
        },
    )
    assert r.status_code == 201, r.text
    after = engine.get(q, headers=bearer(tenant_a.tokens["VIEWER"])).json()
    assert after["lti_count"] == 1 and after["lost_days"] == 4
    assert abs(D(after["ltifr"]) - D(1_000_000) / 63000) < D("0.000001")


def test_incident_rules(tenant_a):
    rest = Rest(tenant_a.tokens["FACILITY_MANAGER"])
    base = {
        "company_id": tenant_a.company_id,
        "facility_id": tenant_a.facility_id,
        "occurred_on": "2024-02-20",
        "severity": "critical",
    }
    assert rest.post("incidents", {**base, "type": "fatality", "fatalities": 0}).status_code >= 400
    assert rest.post("incidents", {**base, "type": "near_miss", "lost_days": 3}).status_code >= 400
    assert Rest(tenant_a.tokens["VIEWER"]).post("incidents", {**base, "type": "near_miss"}).status_code in (401, 403)


def test_module_tables_are_tenant_isolated(tenant_b):
    rest = Rest(tenant_b.tokens["COMPANY_ADMIN"])
    for table in ("labour_monthly", "incidents", "wq_samples", "denominators"):
        assert rest.get(table).json() == [], table


def test_db_rejects_wq_sample_for_unknown_parameter(superuser_conn, tenant_a):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        superuser_conn.execute(
            "insert into public.wq_samples (company_id, facility_id, sample_date, parameter_key, value) "
            "values (%s, %s, '2025-01-01', 'nope', 1)",
            (tenant_a.company_id, tenant_a.facility_id),
        )
