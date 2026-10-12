"""Calculation engine and unit conversion (PRD Features 6 and 7). Pure unit tests, no database.

Fixture values are the published DESNZ 2025 diesel (100% mineral) factors: 2.66155 kg CO2e/L and
3203.91143 kg CO2e/t. They are used here only as test inputs.
"""

from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from app.calc.engine import Activity, Factor, calculate_emissions, resolve_factor
from app.calc.units import FactorConversion, FxRate, UnitGraph, to_factor_unit

GRAPH = UnitGraph(
    {"kg": "mass", "t": "mass", "L": "volume", "m3": "volume", "kWh": "energy", "MWh": "energy", "MJ": "energy",
     "GJ": "energy", "km": "distance", "BDT": "currency", "USD": "currency"},
    [("t", "kg", D("1000"), "SI"), ("m3", "L", D("1000"), "SI"), ("MWh", "kWh", D("1000"), "SI"),
     ("kWh", "MJ", D("3.6"), "exact"), ("GJ", "MJ", D("1000"), "SI")],
)
FX = {("USD", "BDT", 2025): FxRate("USD", "BDT", 2025, D("121.920836605034"), "World Bank WDI")}
T0 = datetime(2025, 1, 1, tzinfo=UTC)

DIESEL_T_PER_L = D("3203.91143") / D("2.66155")


def diesel(**overrides) -> Factor:
    base = {
        "id": "f1", "factor_code": "01010000001202-GLOBAL", "version": 1, "taxonomy_node_id": "n1",
        "geography_code": "GLOBAL", "activity_unit": "L", "co2e": D("2.66155"), "co2e_co2": D("2.62818"),
        "co2e_ch4": D("0.00029"), "co2e_n2o": D("0.03308"), "gwp_version": "AR5", "source_name": "DESNZ 2025",
        "source_url": None, "source_year": 2025, "valid_from": date(2025, 1, 1), "valid_to": date(2025, 12, 31),
        "status": "active", "activated_at": T0, "retired_at": None,
        "conversions": (FactorConversion("t", "L", DIESEL_T_PER_L, "DESNZ 2025"),),
    }
    base.update(overrides)
    return Factor(**base)


def test_same_unit_multiplies_directly():
    r = calculate_emissions(Activity(D("1200"), "L", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.status == "CALCULATED"
    assert r.co2e_kg == D("3193.86")
    assert r.conversion is None
    assert r.formula == "1200 L × 2.66155 kg CO2e/L = 3193.86 kg CO2e"


def test_gas_breakdown_sums_to_total():
    r = calculate_emissions(Activity(D("1000"), "L", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.co2e_co2_kg + r.co2e_ch4_kg + r.co2e_n2o_kg == r.co2e_kg


def test_generic_same_dimension_conversion():
    # 2 m3 of diesel = 2000 L
    r = calculate_emissions(Activity(D("2"), "m3", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.factor_unit_qty == D("2000")
    assert r.co2e_kg == D("5323.10")
    assert r.conversion.kind == "generic"


def test_cross_dimension_uses_the_factors_own_conversion_and_reproduces_per_tonne_factor():
    r = calculate_emissions(Activity(D("1"), "t", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.conversion.kind == "factor"
    assert r.co2e_kg.quantize(D("0.00001")) == D("3203.91143")


def test_cross_dimension_chains_generic_then_factor_conversion():
    # 500 kg -> 0.5 t -> litres via the factor's t->L conversion
    r = calculate_emissions(Activity(D("500"), "kg", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.conversion.kind == "factor+generic"
    assert r.co2e_kg.quantize(D("0.000001")) == (D("3203.91143") / 2).quantize(D("0.000001"))


def test_unsupported_unit_is_a_unit_error_not_zero():
    r = calculate_emissions(Activity(D("100"), "km", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.status == "UNIT_ERROR"
    assert r.co2e_kg is None


def test_missing_factor_is_unknown_not_zero():
    r = calculate_emissions(Activity(D("100"), "L", date(2025, 3, 1)), None, GRAPH, FX)
    assert r.status == "UNKNOWN_FACTOR"
    assert r.co2e_kg is None and r.co2e_t is None


def test_currency_uses_cited_fx_for_the_activity_year():
    spend = diesel(activity_unit="USD", co2e=D("0.507"), co2e_co2=None, co2e_ch4=None, co2e_n2o=None, conversions=())
    r = calculate_emissions(Activity(D("121920.836605034"), "BDT", date(2025, 5, 1)), spend, GRAPH, FX)
    assert r.conversion.kind == "fx"
    assert r.factor_unit_qty == D("1000")
    assert r.co2e_kg == D("507.000")


def test_currency_without_fx_rate_is_unit_error():
    spend = diesel(activity_unit="USD", co2e=D("0.5"), conversions=())
    r = calculate_emissions(Activity(D("1000"), "BDT", date(2019, 5, 1)), spend, GRAPH, FX)
    assert r.status == "UNIT_ERROR"


def test_determinism_same_inputs_same_bytes():
    a = calculate_emissions(Activity(D("1234.567"), "kg", date(2025, 3, 1)), diesel(), GRAPH, FX)
    b = calculate_emissions(Activity(D("1234.567"), "kg", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert (a.co2e_kg, a.formula) == (b.co2e_kg, b.formula)
    assert str(a.co2e_kg) == str(b.co2e_kg)


def test_generic_graph_walks_multiple_hops():
    conv = GRAPH.generic("GJ", "kWh")
    assert conv is not None
    assert (D("1") * conv.multiplier).quantize(D("0.0001")) == D("277.7778")
    assert GRAPH.generic("L", "kg") is None, "cross-dimension conversions are never generic"


def test_to_factor_unit_identity():
    assert to_factor_unit("L", "L", (), GRAPH, FX, 2025).multiplier == 1


# -- factor resolution ------------------------------------------------------------------

def test_fallback_country_then_region_then_global():
    g = diesel(id="g", geography_code="GLOBAL")
    bd = diesel(id="bd", geography_code="BD")
    chain = ["BD", "SAS", "GLOBAL"]
    assert resolve_factor([g, bd], chain, date(2025, 6, 1), T0).id == "bd"
    assert resolve_factor([g], chain, date(2025, 6, 1), T0).id == "g"


def test_resolution_respects_validity_period():
    f25 = diesel(id="f25", version=1)
    f26 = diesel(id="f26", version=2, valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
    chain = ["GLOBAL"]
    assert resolve_factor([f25, f26], chain, date(2025, 12, 31), T0).id == "f25"
    assert resolve_factor([f25, f26], chain, date(2026, 1, 1), T0).id == "f26"
    assert resolve_factor([f25, f26], chain, date(2024, 12, 31), T0) is None


def test_resolution_is_pinned_to_library_snapshot():
    later = diesel(id="late", activated_at=datetime(2025, 9, 1, tzinfo=UTC))
    assert resolve_factor([later], ["GLOBAL"], date(2025, 6, 1), datetime(2025, 8, 1, tzinfo=UTC)) is None
    assert resolve_factor([later], ["GLOBAL"], date(2025, 6, 1), datetime(2025, 9, 2, tzinfo=UTC)).id == "late"


def test_retired_factor_still_serves_older_snapshots():
    retired = diesel(id="old", status="retired", retired_at=datetime(2025, 10, 1, tzinfo=UTC))
    assert resolve_factor([retired], ["GLOBAL"], date(2025, 6, 1), datetime(2025, 9, 1, tzinfo=UTC)).id == "old"
    assert resolve_factor([retired], ["GLOBAL"], date(2025, 6, 1), datetime(2025, 11, 1, tzinfo=UTC)) is None


def test_draft_factors_are_never_used():
    assert resolve_factor([diesel(status="draft")], ["GLOBAL"], date(2025, 6, 1), T0) is None


@pytest.mark.parametrize("qty", [D("0"), D("0.0")])
def test_explicit_zero_quantity_is_calculated_as_zero(qty):
    # An explicit zero entered by the user is data, unlike a missing value.
    r = calculate_emissions(Activity(qty, "L", date(2025, 3, 1)), diesel(), GRAPH, FX)
    assert r.status == "CALCULATED" and r.co2e_kg == 0
