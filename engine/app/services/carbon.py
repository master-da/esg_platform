"""Carbon aggregation for dashboards, insights and reports (PRD F16).

Every figure is a SQL sum of current, CALCULATED rows in public.v_current_calcs - never a separately
computed number - so each one drills down to the calculations behind it. Breakdowns group by the
factor-code taxonomy (ltree sub-paths), which keeps dashboard categories identical to calculation
categories: stationary and mobile diesel stay separate unless shown at a rolled-up level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.db import Tx


@dataclass
class Filters:
    project_ids: list[str]
    facility_id: str | None = None
    grade: str | None = None
    path: str | None = None  # ltree prefix, e.g. "s1" or "s3.c06"
    scope: int | None = None
    month: str | None = None  # YYYY-MM of the record period start
    extra: dict = field(default_factory=dict)

    def where(self) -> tuple[str, dict]:
        clauses = ["cc.status = 'CALCULATED'", "cc.project_id = any(%(projects)s::uuid[])"]
        params: dict = {"projects": self.project_ids}
        if self.facility_id:
            clauses.append("cc.facility_id = %(facility)s::uuid")
            params["facility"] = self.facility_id
        if self.grade:
            clauses.append("cc.quality_grade = %(grade)s")
            params["grade"] = self.grade
        if self.path:
            clauses.append("cc.taxonomy_path operator(extensions.<@) %(path)s::extensions.ltree")
            params["path"] = self.path
        if self.scope:
            clauses.append("cc.scope = %(scope)s")
            params["scope"] = self.scope
        if self.month:
            clauses.append("to_char(cc.period_start, 'YYYY-MM') = %(month)s")
            params["month"] = self.month
        return " and ".join(clauses), params


GROUPS = {
    "scope": ("'Scope ' || cc.scope", "'Scope ' || cc.scope"),
    "facility": ("cc.facility_id::text", "f.name"),
    "grade": ("cc.quality_grade", "'Grade ' || cc.quality_grade"),
    "month": ("to_char(cc.period_start, 'YYYY-MM')", "to_char(cc.period_start, 'YYYY-MM')"),
    "project": ("cc.project_id::text", "p.name"),
}


def breakdown(tx: Tx, f: Filters, group_by: str) -> list[dict]:
    """Totals grouped by scope | facility | grade | month | project | path:N (taxonomy level N)."""
    where, params = f.where()
    if group_by.startswith("path:"):
        level = int(group_by.split(":")[1])
        key = (
            f"case when extensions.nlevel(cc.taxonomy_path) >= {level} "
            f"then extensions.subpath(cc.taxonomy_path, 0, {level}) else cc.taxonomy_path end::text"
        )
        rows = tx.all(
            f"""select {key} as key, sum(cc.co2e_t) as co2e_t, count(*) as records
                from public.v_current_calcs cc where {where} group by 1 order by 2 desc""",
            params,
        )
        labels = {
            r["path"]: r["display_path"]
            for r in tx.all(
                "select path, display_path from ref.taxonomy_labels where path = any(%s)", ([r["key"] for r in rows],)
            )
        }
        return [{**r, "label": labels.get(r["key"], r["key"])} for r in rows]
    key, label = GROUPS[group_by]
    return tx.all(
        f"""select {key} as key, {label} as label, sum(cc.co2e_t) as co2e_t, count(*) as records
            from public.v_current_calcs cc
            join public.facilities f on f.id = cc.facility_id
            join public.projects p on p.id = cc.project_id
            where {where} group by 1, 2 order by {"1" if group_by in ("month", "scope", "grade") else "3 desc"}""",
        params,
    )


def total(tx: Tx, f: Filters) -> Decimal | None:
    where, params = f.where()
    return tx.scalar(f"select sum(cc.co2e_t) from public.v_current_calcs cc where {where}", params)


def unknown_count(tx: Tx, project_ids: list[str]) -> int:
    return tx.scalar(
        """select count(*) from public.v_current_calcs where project_id = any(%s::uuid[])
                        and status in ('UNKNOWN_FACTOR', 'UNIT_ERROR')""",
        (project_ids,),
    )


def drill(tx: Tx, f: Filters, limit: int = 500) -> list[dict]:
    """The calculations behind an aggregate (second click opens a row's calculation trail)."""
    where, params = f.where()
    return tx.all(
        f"""select cc.id as calculation_id, cc.supplier_name, f.name as facility, cc.period_start, cc.period_end,
                   cc.input_quantity, cc.input_unit, cc.co2e_t, cc.taxonomy_display, cc.quality_grade, cc.scope,
                   t.name as category
            from public.v_current_calcs cc join public.facilities f on f.id = cc.facility_id
            join ref.terminals t on t.key = cc.terminal_key
            where {where} order by cc.co2e_t desc nulls last limit {int(limit)}""",
        params,
    )


def previous_project(tx: Tx, project: dict) -> dict | None:
    """The comparable earlier project: same company, boundary and period type, starting one year earlier."""
    start = project["start_date"]
    prev_start = date(start.year - 1, start.month, min(start.day, 28))
    return tx.one(
        """select * from public.projects where company_id = %s and boundary_key = %s and period_type = %s
           and start_date between %s and %s order by start_date desc limit 1""",
        (
            project["company_id"],
            project["boundary_key"],
            project["period_type"],
            prev_start,
            date(start.year - 1, start.month, 28),
        ),
    )


def matched_months_delta(current: dict[str, Decimal | None], previous: dict[str, Decimal | None]) -> dict:
    """Year-over-year change over the months present in BOTH periods (matched by calendar month),
    so a part-year is never compared with a full year. None when nothing overlaps."""
    cur_by_mm = {k[-2:]: v for k, v in current.items() if v is not None}
    prev_by_mm = {k[-2:]: v for k, v in previous.items() if v is not None}
    months = sorted(set(cur_by_mm) & set(prev_by_mm))
    if not months:
        return {"pct": None, "months": 0}
    cur = sum((cur_by_mm[m] for m in months), Decimal(0))
    prev = sum((prev_by_mm[m] for m in months), Decimal(0))
    return {
        "pct": None if prev == 0 else (cur - prev) / prev * 100,
        "months": len(months),
        "current": cur,
        "previous": prev,
    }


def monthly(tx: Tx, f: Filters) -> dict[str, Decimal]:
    return {r["key"]: r["co2e_t"] for r in breakdown(tx, f, "month")}
