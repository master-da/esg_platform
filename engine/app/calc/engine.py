"""The ONLY code path that produces an emissions number (PRD Feature 7).

calculate_emissions(activity, factor, ...) is deterministic: Decimal arithmetic, no intermediate
rounding, no AI. When a factor or a unit conversion is missing it returns an UNKNOWN_FACTOR /
UNIT_ERROR result with no number - it never guesses and never returns zero for missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal

from app.calc.units import Conversion, FactorConversion, FxRate, UnitGraph, dmul, to_factor_unit

ENGINE_VERSION = "calc-1.0.0"

# Rounding policy: no intermediate rounding. The final kg CO2e (total and per gas) is rounded once,
# to 6 decimal places (milligrams), half-even. Formula text shows intermediates to at most 10 places.
RESULT_QUANTUM = Decimal("0.000001")
DISPLAY_PLACES = 10


@dataclass(frozen=True)
class Factor:
    id: str
    factor_code: str
    version: int
    taxonomy_node_id: str
    geography_code: str
    activity_unit: str
    co2e: Decimal
    co2e_co2: Decimal | None
    co2e_ch4: Decimal | None
    co2e_n2o: Decimal | None
    gwp_version: str
    source_name: str
    source_url: str | None
    source_year: int
    valid_from: date
    valid_to: date
    status: str
    activated_at: datetime | None
    retired_at: datetime | None
    conversions: tuple[FactorConversion, ...] = field(default=())


@dataclass(frozen=True)
class Activity:
    quantity: Decimal
    unit: str
    period_start: date


@dataclass(frozen=True)
class CalcResult:
    status: str  # CALCULATED | UNKNOWN_FACTOR | UNIT_ERROR
    message: str | None
    factor: Factor | None
    conversion: Conversion | None
    factor_unit_qty: Decimal | None
    co2e_kg: Decimal | None
    co2e_co2_kg: Decimal | None
    co2e_ch4_kg: Decimal | None
    co2e_n2o_kg: Decimal | None
    formula: str | None

    @property
    def co2e_t(self) -> Decimal | None:
        return None if self.co2e_kg is None else self.co2e_kg / 1000


def fmt(d: Decimal, places: int | None = None) -> str:
    """Human-readable rendering of a Decimal for the calculation trail (trailing zeros removed)."""
    if places is not None and d.as_tuple().exponent < -places:
        d = d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
    s = format(d.normalize(), "f")
    return s


def _result(x: Decimal) -> Decimal:
    return x.quantize(RESULT_QUANTUM, rounding=ROUND_HALF_EVEN)


def resolve_factor(
    candidates: list[Factor], geography_chain: list[str], on_date: date, library_as_of: datetime
) -> Factor | None:
    """Country -> region -> global fallback (PRD F6). Only factors that were active in the library
    at `library_as_of` (the calculation version's snapshot time) and valid on `on_date` qualify."""

    def eligible(f: Factor) -> bool:
        if f.status not in ("active", "retired") or f.activated_at is None or f.activated_at > library_as_of:
            return False
        if f.retired_at is not None and f.retired_at <= library_as_of:
            return False
        return f.valid_from <= on_date <= f.valid_to

    for geo in geography_chain:
        matches = [f for f in candidates if f.geography_code == geo and eligible(f)]
        if matches:
            return max(matches, key=lambda f: (f.version, f.factor_code))
    return None


def calculate_emissions(
    activity: Activity, factor: Factor | None, graph: UnitGraph, fx: dict[tuple[str, str, int], FxRate]
) -> CalcResult:
    if factor is None:
        return CalcResult(
            "UNKNOWN_FACTOR",
            "No active emission factor is available for this category, "
            "geography and period. Request a factor from the library team.",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    conversion = to_factor_unit(
        activity.unit, factor.activity_unit, factor.conversions, graph, fx, activity.period_start.year
    )
    if conversion is None:
        return CalcResult(
            "UNIT_ERROR",
            f"Cannot convert {activity.unit} to {factor.activity_unit}: the factor has "
            "no conversion for this unit. Re-enter the data in a supported unit.",
            factor,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    qty = dmul(activity.quantity, conversion.multiplier)
    co2e = _result(dmul(qty, factor.co2e))
    per_gas = [
        None if g is None else _result(dmul(qty, g)) for g in (factor.co2e_co2, factor.co2e_ch4, factor.co2e_n2o)
    ]

    steps = []
    p = DISPLAY_PLACES
    if conversion.multiplier != 1 or conversion.from_unit != conversion.to_unit:
        steps.append(
            f"{fmt(activity.quantity)} {activity.unit} × {fmt(conversion.multiplier, p)} "
            f"{factor.activity_unit}/{activity.unit} = {fmt(qty, p)} {factor.activity_unit}"
        )
    steps.append(
        f"{fmt(qty, p)} {factor.activity_unit} × {fmt(factor.co2e)} kg CO2e/{factor.activity_unit} "
        f"= {fmt(co2e)} kg CO2e"
    )
    return CalcResult(
        "CALCULATED", None, factor, conversion if steps[:-1] else None, qty, co2e, *per_gas, "; ".join(steps)
    )
