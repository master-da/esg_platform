"""Upload validation engine (PRD Feature 5.2).

Each terminal's rule set lives in its configuration (ref.terminals.config.rules plus per-column
types/required/options). This module only implements the generic rule types once, so adding or
changing a category's rules is a configuration change that cannot affect other categories.

Every issue names the spreadsheet row and the field at fault, with a fix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingest.parser import ParsedFile
from app.ingest.terminal import Column, Terminal, norm


@dataclass(frozen=True)
class Issue:
    row: int | None
    field: str | None
    problem: str
    fix: str | None = None
    severity: str = "error"


@dataclass
class ValidRow:
    source_row: int
    values: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationContext:
    facilities: dict[str, tuple[str, str]]  # norm(name) -> (id, display name)
    unit_dimensions: dict[str, str]  # unit code -> dimension
    unit_aliases: dict[str, str]  # norm(code or name) -> code
    project_start: date
    project_end: date


_DMY = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _parse_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = _DMY.match(s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _parse_decimal(v: Any) -> Decimal | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, Decimal)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))  # shortest round-trip representation, deterministic
    s = str(v).strip().replace(",", "").replace(" ", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _cell(col: Column, raw: Any, ctx: ValidationContext, row: int) -> tuple[Any, Issue | None]:
    if _blank(raw):
        if col.required:
            return None, Issue(row, col.header, "Required field is empty", f"Enter a {col.header.lower()}")
        return None, None
    if col.type == "date":
        d = _parse_date(raw)
        return (
            (d, None)
            if d
            else (None, Issue(row, col.header, f'"{raw}" is not a valid date', "Use the format YYYY-MM-DD"))
        )
    if col.type in ("decimal", "integer"):
        d = _parse_decimal(raw)
        if d is None or (col.type == "integer" and d != d.to_integral_value()):
            kind = "a whole number" if col.type == "integer" else "a number"
            return None, Issue(row, col.header, f'"{raw}" is not {kind}', f"Enter {kind} in {col.header}")
        if col.min is not None and d < Decimal(str(col.min)):
            return None, Issue(
                row,
                col.header,
                f"Value {raw} is below the minimum of {col.min:g}",
                f"Enter a value of at least {col.min:g}",
            )
        if col.max is not None and d > Decimal(str(col.max)):
            return None, Issue(
                row,
                col.header,
                f"Value {raw} is above the maximum of {col.max:g}",
                f"Enter a value of at most {col.max:g}",
            )
        return d, None
    if col.type == "enum":
        lookup = {norm(o): o for o in col.options}
        hit = lookup.get(norm(raw))
        if hit is None:
            return None, Issue(
                row,
                col.header,
                f'"{raw}" is not in the {col.header.lower()} list',
                f"Pick a listed {col.header.lower()}",
            )
        return hit, None
    if col.type == "unit":
        code = ctx.unit_aliases.get(norm(raw))
        if code is None or code not in col.options:
            return None, Issue(
                row, col.header, f'"{raw}" is not an accepted unit here', "Use one of: " + ", ".join(col.options)
            )
        return code, None
    if col.type == "facility":
        hit = ctx.facilities.get(norm(raw))
        if hit is None:
            return None, Issue(
                row,
                col.header,
                f'Facility "{raw}" does not exist in this company',
                "Use a facility name from Company & facilities (the template dropdown lists them)",
            )
        return hit[0], None
    return str(raw).strip(), None


def validate(parsed: ParsedFile, terminal: Terminal, ctx: ValidationContext) -> tuple[list[ValidRow], list[Issue]]:
    issues: list[Issue] = []
    header_map: dict[str, str] = {}
    present = {norm(h): h for h in parsed.headers if h}
    for col in terminal.columns:
        actual = present.get(norm(col.header))
        if actual is None:
            if col.required:
                issues.append(
                    Issue(
                        None,
                        col.header,
                        f'Column "{col.header}" is missing',
                        "Download the latest template for this category and copy your data into it",
                    )
                )
        else:
            header_map[col.key] = actual
    if issues:
        return [], issues
    if not parsed.rows:
        return [], [Issue(None, None, "The file contains no data rows", "Fill in at least one row below the header")]

    unit_col = terminal.role("unit")
    rows: list[ValidRow] = []
    for row_no, raw in parsed.rows:
        values: dict[str, Any] = {}
        row_issues: list[Issue] = []
        for col in terminal.columns:
            value, issue = _cell(col, raw.get(header_map.get(col.key, ""), None), ctx, row_no)
            values[col.key] = value
            if issue:
                row_issues.append(issue)
        row_issues += _apply_rules(terminal, values, ctx, row_no, unit_col)
        issues += row_issues
        rows.append(ValidRow(row_no, values, raw))
    return rows, issues


def _apply_rules(
    terminal: Terminal, values: dict[str, Any], ctx: ValidationContext, row: int, unit_col: Column | None
) -> list[Issue]:
    out: list[Issue] = []
    unit = values.get(unit_col.key) if unit_col else None
    for rule in terminal.rules:
        kind = rule["type"]
        if kind == "unit_dimension_in" and unit:
            dim = ctx.unit_dimensions.get(unit)
            if dim not in rule["dimensions"]:
                out.append(
                    Issue(
                        row,
                        unit_col.header,
                        rule.get("problem") or f"A {dim} unit is not accepted here",
                        rule.get("fix"),
                    )
                )
        elif kind == "unit_must_be" and unit:
            if unit not in rule["units"]:
                dim = ctx.unit_dimensions.get(unit, "")
                problem = (
                    rule.get("problem")
                    or f"{dim.capitalize()} figure entered under a {'/'.join(rule['units'])}-only column"
                )
                out.append(Issue(row, unit_col.header, problem, rule.get("fix") or "Change the unit or the column"))
        elif kind == "period_order":
            s, e = values.get("period_start"), values.get("period_end")
            if s and e and s > e:
                out.append(
                    Issue(
                        row,
                        terminal.column("period_end").header,
                        "Period end is before period start",
                        "Check the two dates",
                    )
                )
        elif kind == "period_within_project":
            s, e = values.get("period_start"), values.get("period_end")
            if s and e and (s < ctx.project_start or e > ctx.project_end):
                out.append(
                    Issue(
                        row,
                        terminal.column("period_start").header,
                        f"Period {s} to {e} is outside the project period {ctx.project_start} to {ctx.project_end}",
                        "Upload this row to the project that covers its period",
                    )
                )
        elif kind == "unit_by_value" and unit:
            # e.g. flights must be in passenger-km, hotel stays in room-nights
            chosen = values.get(rule["column"])
            allowed = rule["allowed"].get(chosen) if chosen else None
            if allowed and unit not in allowed:
                out.append(
                    Issue(
                        row,
                        unit_col.header,
                        f"{unit} is not a valid unit for {chosen}",
                        "Use " + " or ".join(allowed),
                    )
                )
        elif kind == "required_if":
            when = rule["when"]
            if all(norm(values.get(k) or "") == norm(v) for k, v in when.items()) and _blank(
                values.get(rule["column"])
            ):
                col = terminal.column(rule["column"])
                out.append(
                    Issue(
                        row,
                        col.header if col else rule["column"],
                        rule.get("problem") or "Required field is empty",
                        rule.get("fix"),
                    )
                )
    return out
