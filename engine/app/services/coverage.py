"""Missing-data detection (PRD 5.1: "Missing is never zero").

For every in-scope category, each facility that reported in it is expected to report every month of
the project period. A month that no record's period overlaps is Missing. Categories marked not
applicable are reported as N/A with their reason; explicit zero quantities count as data.
"""

from __future__ import annotations

from datetime import date

from app.db import Tx


def months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def _month_end(m: date) -> date:
    nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def coverage(tx: Tx, project: dict, modules: tuple[str, ...] | None = None) -> list[dict]:
    rows = tx.all(
        """select r.terminal_key, t.name as terminal_name, t.module, r.facility_id, f.name as facility,
                  r.period_start, r.period_end
           from public.activity_records r
           join ref.terminals t on t.key = r.terminal_key
           join public.facilities f on f.id = r.facility_id
           join public.project_categories pc on pc.project_id = r.project_id and pc.terminal_key = r.terminal_key
           where r.project_id = %s and r.deleted_at is null and pc.in_scope""",
        (project["id"],),
    )
    expected = months(project["start_date"], project["end_date"])
    groups: dict[tuple[str, str], dict] = {}
    for r in rows:
        if modules and r["module"] not in modules:
            continue
        g = groups.setdefault(
            (r["terminal_key"], str(r["facility_id"])),
            {
                "terminal_key": r["terminal_key"],
                "terminal_name": r["terminal_name"],
                "module": r["module"],
                "facility_id": str(r["facility_id"]),
                "facility": r["facility"],
                "periods": [],
            },
        )
        g["periods"].append((r["period_start"], r["period_end"]))
    out = []
    for g in groups.values():
        missing = [m for m in expected if not any(s <= _month_end(m) and e >= m for s, e in g["periods"])]
        out.append(
            {k: v for k, v in g.items() if k != "periods"}
            | {
                "expected_months": len(expected),
                "covered_months": len(expected) - len(missing),
                "missing_months": [m.strftime("%Y-%m") for m in missing],
            }
        )
    return sorted(out, key=lambda x: (x["terminal_name"], x["facility"]))
