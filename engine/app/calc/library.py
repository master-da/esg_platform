"""Load calculation inputs (units, FX, factors, geography chains) from the library schemas."""

from __future__ import annotations

from decimal import Decimal

from app.calc.engine import Factor
from app.calc.units import FactorConversion, FxRate, UnitGraph
from app.db import Tx


def load_unit_graph(tx: Tx) -> UnitGraph:
    units = {r["code"]: r["dimension"] for r in tx.all("select code, dimension from ref.units")}
    edges = [(r["from_unit"], r["to_unit"], Decimal(r["multiplier"]), r["definition"])
             for r in tx.all("select from_unit, to_unit, multiplier, definition from ref.unit_conversions")]
    return UnitGraph(units, edges)


def load_fx(tx: Tx) -> dict[tuple[str, str, int], FxRate]:
    with tx.privileged():
        rows = tx.all("select base_currency, quote_currency, year, rate, source_name from lib.fx_rates")
    return {(r["base_currency"], r["quote_currency"], r["year"]):
            FxRate(r["base_currency"], r["quote_currency"], r["year"], Decimal(r["rate"]), r["source_name"])
            for r in rows}


def geography_chain(tx: Tx, country_code: str | None) -> list[str]:
    """Country -> its region(s) -> GLOBAL."""
    chain: list[str] = []
    code = tx.scalar("select code from ref.geographies where country_code = %s and level = 'country'", (country_code,))
    while code:
        chain.append(code)
        code = tx.scalar("select parent_code from ref.geographies where code = %s", (code,))
    if "GLOBAL" not in chain:
        chain.append("GLOBAL")
    return chain


def load_factors(tx: Tx, node_ids: list[str]) -> dict[str, list[Factor]]:
    if not node_ids:
        return {}
    with tx.privileged():
        rows = tx.all(
            """select * from lib.emission_factors
               where taxonomy_node_id = any(%s::uuid[]) and status in ('active', 'retired')""", (node_ids,))
        conv = tx.all(
            """select emission_factor_id, from_unit, to_unit, multiplier, source_name, note
               from lib.factor_conversions where emission_factor_id = any(%s::uuid[])""",
            ([r["id"] for r in rows],))
    by_factor: dict[str, list[FactorConversion]] = {}
    for c in conv:
        by_factor.setdefault(str(c["emission_factor_id"]), []).append(
            FactorConversion(c["from_unit"], c["to_unit"], Decimal(c["multiplier"]), c["source_name"], c["note"]))
    out: dict[str, list[Factor]] = {}
    for r in rows:
        f = Factor(
            id=str(r["id"]), factor_code=r["factor_code"], version=r["version"],
            taxonomy_node_id=str(r["taxonomy_node_id"]), geography_code=r["geography_code"],
            activity_unit=r["activity_unit"], co2e=Decimal(r["co2e"]),
            co2e_co2=None if r["co2e_co2"] is None else Decimal(r["co2e_co2"]),
            co2e_ch4=None if r["co2e_ch4"] is None else Decimal(r["co2e_ch4"]),
            co2e_n2o=None if r["co2e_n2o"] is None else Decimal(r["co2e_n2o"]),
            gwp_version=r["gwp_version"], source_name=r["source_name"], source_url=r["source_url"],
            source_year=r["source_year"], valid_from=r["valid_from"], valid_to=r["valid_to"], status=r["status"],
            activated_at=r["activated_at"], retired_at=r["retired_at"],
            conversions=tuple(by_factor.get(str(r["id"]), [])),
        )
        out.setdefault(f.taxonomy_node_id, []).append(f)
    return out
