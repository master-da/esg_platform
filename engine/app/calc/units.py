"""Unit conversion service (PRD Feature 6, "Unit conversion").

* Generic conversions stay within one dimension and come only from exact unit definitions
  (ref.unit_conversions), e.g. t <-> kg, m3 <-> L, MWh <-> kWh.
* A cross-dimension conversion (e.g. tonnes of diesel -> litres) uses ONLY the matched factor's
  own conversion factors (lib.factor_conversions).
* Currency -> currency uses a cited FX rate for the activity year (lib.fx_rates).
* Everything is Decimal; the same inputs always give the same output.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, localcontext

PRECISION = 34


def dmul(*xs: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        out = Decimal(1)
        for x in xs:
            out = out * x
        return +out


def ddiv(a: Decimal, b: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return a / b


@dataclass(frozen=True)
class Conversion:
    from_unit: str
    to_unit: str
    multiplier: Decimal
    kind: str                      # generic | factor | fx | factor+generic
    source: str                    # definition / citation shown in the calculation trail


class UnitGraph:
    def __init__(self, dimensions: dict[str, str], edges: list[tuple[str, str, Decimal, str]]):
        self.dimensions = dimensions
        self._adj: dict[str, list[tuple[str, Decimal, str]]] = {u: [] for u in dimensions}
        for frm, to, mult, definition in edges:
            self._adj.setdefault(frm, []).append((to, Decimal(mult), definition))
            self._adj.setdefault(to, []).append((frm, ddiv(Decimal(1), Decimal(mult)), definition))
        for k in self._adj:
            self._adj[k].sort(key=lambda e: e[0])   # deterministic traversal

    def dimension(self, unit: str) -> str | None:
        return self.dimensions.get(unit)

    def generic(self, frm: str, to: str) -> Conversion | None:
        """Same-dimension conversion via exact definitions (breadth-first, deterministic)."""
        if frm == to:
            return Conversion(frm, to, Decimal(1), "generic", "identity")
        if self.dimension(frm) is None or self.dimension(frm) != self.dimension(to):
            return None
        seen = {frm}
        queue: deque[tuple[str, Decimal, list[str]]] = deque([(frm, Decimal(1), [])])
        while queue:
            unit, mult, defs = queue.popleft()
            for nxt, m, definition in self._adj.get(unit, []):
                if nxt in seen:
                    continue
                total = dmul(mult, m)
                if nxt == to:
                    return Conversion(frm, to, total, "generic", "; ".join([*defs, definition]))
                seen.add(nxt)
                queue.append((nxt, total, [*defs, definition]))
        return None


@dataclass(frozen=True)
class FactorConversion:
    from_unit: str
    to_unit: str
    multiplier: Decimal
    source_name: str
    note: str | None = None


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    year: int
    rate: Decimal        # quote per 1 base
    source_name: str


def to_factor_unit(qty_unit: str, factor_unit: str, factor_conversions: tuple[FactorConversion, ...],
                   graph: UnitGraph, fx: dict[tuple[str, str, int], FxRate], year: int) -> Conversion | None:
    """Find the multiplier that turns `qty_unit` into the factor's activity unit, or None."""
    generic = graph.generic(qty_unit, factor_unit)
    if generic is not None:
        return generic

    if graph.dimension(qty_unit) == "currency" and graph.dimension(factor_unit) == "currency":
        direct = fx.get((factor_unit, qty_unit, year))      # e.g. USD->BDT rate: BDT per USD
        if direct:
            return Conversion(qty_unit, factor_unit, ddiv(Decimal(1), direct.rate), "fx",
                              f"{direct.source_name}, {year}: {direct.rate} {qty_unit} per {factor_unit}")
        inverse = fx.get((qty_unit, factor_unit, year))
        if inverse:
            return Conversion(qty_unit, factor_unit, inverse.rate, "fx",
                              f"{inverse.source_name}, {year}: {inverse.rate} {factor_unit} per {qty_unit}")
        return None

    for fc in sorted(factor_conversions, key=lambda c: (c.from_unit, c.to_unit)):
        # The factor's conversion goes fc.from_unit -> fc.to_unit (= the factor unit). Reach fc.from_unit generically.
        if fc.to_unit != factor_unit:
            continue
        lead = graph.generic(qty_unit, fc.from_unit)
        if lead is None:
            continue
        kind = "factor" if lead.multiplier == 1 and qty_unit == fc.from_unit else "factor+generic"
        source = fc.source_name + (f" ({fc.note})" if fc.note else "")
        if kind == "factor+generic":
            source = f"{lead.source}; {source}"
        return Conversion(qty_unit, factor_unit, dmul(lead.multiplier, fc.multiplier), kind, source)
    return None
