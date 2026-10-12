"""Energy, water, waste, labour and safety figures (PRD Features 8-13).

Rules shared by every module:
  * Missing is never zero: a month a reporting facility did not cover is listed as missing, and any
    ratio that depends on missing data is returned as None (shown as "Missing").
  * Quantities are aggregated from activity_records / module tables; nothing is estimated.
  * A record spanning several months is allocated to months pro rata by days.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calc.units import ddiv, dmul
from app.db import Tx
from app.services.coverage import coverage, months

ENERGY_SOURCES = {
    "s2_electricity": "electricity",
    "s2_heating": "heat_steam_cooling",
    "s2_steam": "heat_steam_cooling",
    "s2_cooling": "heat_steam_cooling",
    "s1_stationary": "fuels_stationary",
    "s1_mobile": "fuels_mobile",
    "energy_renewable": "renewable",
}


def allocate(qty: Decimal, start: date, end: date) -> dict[str, Decimal]:
    """Split a quantity over calendar months in proportion to days covered."""
    days = (end - start).days + 1
    out: dict[str, Decimal] = {}
    d = start
    while d <= end:
        month_end = date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1)
        span = (min(end, month_end) - d).days + 1
        key = d.strftime("%Y-%m")
        out[key] = out.get(key, Decimal(0)) + ddiv(dmul(qty, Decimal(span)), Decimal(days))
        d = month_end + timedelta(days=1)
    return out


def _missing_by(cov: list[dict], key_fn) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for c in cov:
        k = key_fn(c)
        if k:
            out.setdefault(k, set()).update(c["missing_months"])
    return out


def _month_keys(project: dict) -> list[str]:
    return [m.strftime("%Y-%m") for m in months(project["start_date"], project["end_date"])]


# -- Energy (F8) --------------------------------------------------------------------------


def energy(tx: Tx, project: dict, denominator_kind: str | None = None) -> dict:
    rows = tx.all(
        """select r.id, r.terminal_key, r.facility_id, f.name as facility, r.period_start, r.period_end,
                  r.normalized_quantity, r.normalized_unit, r.review_status, cc.status as calc_status,
                  cc.emission_factor_id, cc.factor_unit_quantity, cc.factor_unit
           from public.activity_records r
           join public.facilities f on f.id = r.facility_id
           left join public.v_current_calcs cc on cc.activity_record_id = r.id
           where r.project_id = %s and r.deleted_at is null and r.terminal_key = any(%s)""",
        (project["id"], list(ENERGY_SOURCES)),
    )
    factor_ids = sorted({str(r["emission_factor_id"]) for r in rows if r["emission_factor_id"]})
    kwh_conv: dict[str, Decimal] = {}
    if factor_ids:
        with tx.privileged():
            for c in tx.all(
                """select emission_factor_id, to_unit, multiplier from lib.factor_conversions
                   where emission_factor_id = any(%s::uuid[]) and from_unit = 'kWh'""",
                (factor_ids,),
            ):
                kwh_conv[str(c["emission_factor_id"])] = Decimal(c["multiplier"])  # 1 kWh = m factor-units

    month_keys = _month_keys(project)
    monthly = {m: {s: Decimal(0) for s in set(ENERGY_SOURCES.values())} for m in month_keys}
    totals = dict.fromkeys(set(ENERGY_SOURCES.values()), Decimal(0))
    by_facility: dict[str, Decimal] = {}
    unconverted = []
    for r in rows:
        source = ENERGY_SOURCES[r["terminal_key"]]
        kwh: Decimal | None = None
        if r["normalized_unit"] == "kWh":
            kwh = Decimal(r["normalized_quantity"])
        elif (
            r["calc_status"] == "CALCULATED"
            and str(r["emission_factor_id"]) in kwh_conv
            and r["factor_unit_quantity"] is not None
        ):
            kwh = ddiv(Decimal(r["factor_unit_quantity"]), kwh_conv[str(r["emission_factor_id"])])
        if kwh is None:
            unconverted.append(
                {
                    "record_id": str(r["id"]),
                    "terminal_key": r["terminal_key"],
                    "facility": r["facility"],
                    "quantity": r["normalized_quantity"],
                    "unit": r["normalized_unit"],
                }
            )
            continue
        totals[source] += kwh
        by_facility[r["facility"]] = by_facility.get(r["facility"], Decimal(0)) + kwh
        for m, part in allocate(kwh, r["period_start"], r["period_end"]).items():
            if m in monthly:
                monthly[m][source] += part

    cov = coverage(tx, project)
    missing = _missing_by(cov, lambda c: ENERGY_SOURCES.get(c["terminal_key"]))
    reported = {ENERGY_SOURCES[r["terminal_key"]] for r in rows}
    total = sum(totals.values(), Decimal(0))
    renewable_share = ddiv(totals["renewable"] * 100, total) if total else None

    denominators = tx.all(
        """select d.kind, d.value, d.unit, d.facility_id, f.name as facility from public.denominators d
           left join public.facilities f on f.id = d.facility_id where d.project_id = %s""",
        (project["id"],),
    )
    intensity = None
    if denominator_kind:
        company_level = [d for d in denominators if d["kind"] == denominator_kind and d["facility_id"] is None]
        if company_level:
            denom, unit = Decimal(company_level[0]["value"]), company_level[0]["unit"]
        else:
            facility_rows = {
                d["facility"]: d for d in denominators if d["kind"] == denominator_kind and d["facility_id"] is not None
            }
            covered = set(by_facility) <= set(facility_rows)
            denom = sum((Decimal(d["value"]) for d in facility_rows.values()), Decimal(0)) if covered else None
            units = {d["unit"] for d in facility_rows.values()}
            unit = units.pop() if len(units) == 1 else None
            if unit is None:
                denom = None
        intensity = {
            "kind": denominator_kind,
            "denominator": denom,
            "denominator_unit": unit,
            "value": ddiv(total, denom) if denom and total else None,
        }
    gaps = sorted({m for s in reported for m in missing.get(s, set())})
    return {
        "total_kwh": total if rows else None,
        "missing_months": gaps,
        "by_source_kwh": {s: (v if s in reported else None) for s, v in totals.items()},
        "renewable_share_pct": renewable_share,
        "by_facility_kwh": by_facility,
        "monthly": [
            {
                "month": m,
                **{
                    s: (None if (s in reported and m in missing.get(s, set())) else (v if s in reported else None))
                    for s, v in vals.items()
                },
                "missing": sorted(s for s in reported if m in missing.get(s, set())),
            }
            for m, vals in monthly.items()
        ],
        "unconverted": unconverted,
        "denominators": denominators,
        "intensity": intensity,
    }


# -- Water (F9) ---------------------------------------------------------------------------


def water(tx: Tx, project: dict) -> dict:
    rows = tx.all(
        """select r.id, r.terminal_key, r.facility_id, f.name as facility, r.period_start, r.period_end,
                  r.normalized_quantity, r.normalized_unit, r.attributes, r.review_status, r.source_type
           from public.activity_records r join public.facilities f on f.id = r.facility_id
           where r.project_id = %s and r.deleted_at is null and r.terminal_key in ('water_withdrawal', 'water_discharge')
           order by r.period_start""",
        (project["id"],),
    )
    month_keys = _month_keys(project)
    by_source: dict[str, Decimal] = {}
    by_destination: dict[str, Decimal] = {}
    fac_month: dict[tuple[str, str, str], Decimal] = {}
    monthly = {m: {"withdrawal": Decimal(0), "discharge": Decimal(0)} for m in month_keys}
    for r in rows:
        q = Decimal(r["normalized_quantity"])
        kind = "withdrawal" if r["terminal_key"] == "water_withdrawal" else "discharge"
        label = r["attributes"].get("source") if kind == "withdrawal" else r["attributes"].get("destination")
        target = by_source if kind == "withdrawal" else by_destination
        target[label] = target.get(label, Decimal(0)) + q
        for m, part in allocate(q, r["period_start"], r["period_end"]).items():
            if m in monthly:
                monthly[m][kind] += part
                fac_month[(kind, r["facility"], m)] = fac_month.get((kind, r["facility"], m), Decimal(0)) + part
    cov = coverage(tx, project, modules=("water",))
    missing = _missing_by(cov, lambda c: "withdrawal" if c["terminal_key"] == "water_withdrawal" else "discharge")
    has = {("withdrawal" if r["terminal_key"] == "water_withdrawal" else "discharge") for r in rows}
    # Consumption only where both withdrawal and discharge exist for the same facility-month.
    consumption = Decimal(0)
    consumption_months = 0
    for (kind, fac, m), w in fac_month.items():
        if kind == "withdrawal" and ("discharge", fac, m) in fac_month:
            consumption += w - fac_month[("discharge", fac, m)]
            consumption_months += 1
    return {
        "withdrawal_m3": sum(by_source.values(), Decimal(0)) if "withdrawal" in has else None,
        "discharge_m3": sum(by_destination.values(), Decimal(0)) if "discharge" in has else None,
        "consumption_m3": consumption if consumption_months else None,
        "consumption_basis": f"{consumption_months} facility-months with both withdrawal and discharge",
        "by_source": by_source,
        "by_destination": by_destination,
        "monthly": [
            {
                "month": m,
                "withdrawal": None
                if ("withdrawal" in has and m in missing.get("withdrawal", set())) or "withdrawal" not in has
                else v["withdrawal"],
                "discharge": None
                if ("discharge" in has and m in missing.get("discharge", set())) or "discharge" not in has
                else v["discharge"],
                "missing": sorted(k for k in has if m in missing.get(k, set())),
            }
            for m, v in monthly.items()
        ],
        "records": rows,
        "verification": {
            "verified": sum(r["review_status"] == "USER_VERIFIED" for r in rows),
            "pending": sum(r["review_status"] != "USER_VERIFIED" for r in rows),
        },
    }


# -- Waste (F11) --------------------------------------------------------------------------


def waste(tx: Tx, project: dict) -> dict:
    params = tx.scalar("select params from ref.metrics where key = 'WASTE_RECYCLED'") or {}
    recycled_routes = set(params.get("treatments", ["Reuse", "Recycling", "Composting"]))
    rows = tx.all(
        """select r.id, f.name as facility, r.period_start, r.period_end, r.normalized_quantity, r.normalized_unit,
                  r.attributes, r.supplier_name, cc.status as calc_status, cc.co2e_t
           from public.activity_records r join public.facilities f on f.id = r.facility_id
           left join public.v_current_calcs cc on cc.activity_record_id = r.id
           where r.project_id = %s and r.deleted_at is null and r.terminal_key = 's3_c05'
           order by r.period_start""",
        (project["id"],),
    )
    total = hazardous = recycled = Decimal(0)
    by_treatment: dict[str, Decimal] = {}
    by_type: dict[str, Decimal] = {}
    for r in rows:
        t = ddiv(Decimal(r["normalized_quantity"]), Decimal(1000))  # kg -> t
        r["quantity_t"] = t
        r["hazardous"] = r["attributes"].get("hazardous") == "Yes"
        total += t
        if r["hazardous"]:
            hazardous += t
        treatment = r["attributes"].get("treatment") or "Other"
        by_treatment[treatment] = by_treatment.get(treatment, Decimal(0)) + t
        wt = r["attributes"].get("waste_type") or "Other"
        by_type[wt] = by_type.get(wt, Decimal(0)) + t
        if treatment in recycled_routes:
            recycled += t
    cov = coverage(tx, project)
    gaps = [c for c in cov if c["terminal_key"] == "s3_c05" and c["missing_months"]]
    return {
        "total_t": total if rows else None,
        "hazardous_t": hazardous if rows else None,
        "non_hazardous_t": total - hazardous if rows else None,
        "recycled_t": recycled if rows else None,
        "recycling_rate_pct": ddiv(recycled * 100, total) if total else None,
        "recycling_definition": "Waste sent to " + ", ".join(sorted(recycled_routes)) + " ÷ total waste, by mass",
        "by_treatment": by_treatment,
        "by_type": by_type,
        "co2e_t": sum((Decimal(r["co2e_t"]) for r in rows if r["calc_status"] == "CALCULATED"), Decimal(0))
        if rows
        else None,
        "records": rows,
        "missing": gaps,
    }


# -- Labour (F12) -------------------------------------------------------------------------


def labour(tx: Tx, company_id: str, start: date, end: date, facility_id: str | None = None) -> dict:
    rows = tx.all(
        """select l.*, f.name as facility from public.labour_monthly l join public.facilities f on f.id = l.facility_id
           where l.company_id = %s and l.month between %s and %s and (%s::uuid is null or l.facility_id = %s::uuid)
           order by l.month, f.name""",
        (company_id, date(start.year, start.month, 1), end, facility_id, facility_id),
    )
    expected = [m.strftime("%Y-%m") for m in months(start, end)]
    facilities = sorted({r["facility"] for r in rows})
    have = {(r["facility"], r["month"].strftime("%Y-%m")) for r in rows}
    missing = {f: [m for m in expected if (f, m) not in have] for f in facilities}
    monthly = []
    for m in expected:
        mr = [r for r in rows if r["month"].strftime("%Y-%m") == m]
        gap = [f for f in facilities if m in missing[f]]
        head = sum(r["headcount_permanent"] + r["headcount_temporary"] for r in mr)
        monthly.append(
            {
                "month": m,
                "complete": not gap and bool(mr),
                "missing_facilities": gap,
                "headcount": head if mr else None,
                "permanent": sum(r["headcount_permanent"] for r in mr) if mr else None,
                "temporary": sum(r["headcount_temporary"] for r in mr) if mr else None,
                "female": sum(r["headcount_female"] for r in mr) if mr else None,
                "male": sum(r["headcount_male"] for r in mr) if mr else None,
                "other": sum(r["headcount_other"] for r in mr) if mr else None,
                "new_hires": sum(r["new_hires"] for r in mr) if mr else None,
                "departures": sum(r["departures"] for r in mr) if mr else None,
                "training_hours": sum((Decimal(r["training_hours"] or 0) for r in mr), Decimal(0)) if mr else None,
            }
        )
    complete = bool(rows) and all(m["complete"] for m in monthly)
    heads = [Decimal(m["headcount"]) for m in monthly if m["headcount"] is not None]
    avg_head = ddiv(sum(heads, Decimal(0)), Decimal(len(heads))) if heads else None
    departures = sum(m["departures"] or 0 for m in monthly)
    training = sum((m["training_hours"] or Decimal(0) for m in monthly), Decimal(0))
    hours_known = complete and all(r["working_hours"] is not None for r in rows)
    hours = sum((Decimal(r["working_hours"] or 0) + Decimal(r["overtime_hours"] or 0) for r in rows), Decimal(0))
    return {
        "months": expected,
        "monthly": monthly,
        "complete": complete,
        "missing": {f: m for f, m in missing.items() if m},
        "headcount_avg": avg_head if complete else None,
        "latest_headcount": monthly[-1]["headcount"] if monthly and monthly[-1]["headcount"] is not None else None,
        "new_hires": sum(m["new_hires"] or 0 for m in monthly) if complete else None,
        "departures": departures if complete else None,
        "turnover_rate_pct": ddiv(Decimal(departures) * 100, avg_head) if complete and avg_head else None,
        "training_hours": training if complete else None,
        "training_hours_per_employee": ddiv(training, avg_head) if complete and avg_head else None,
        "hours_worked": hours if hours_known else None,
    }


# -- Health & safety (F13) ----------------------------------------------------------------


def safety(tx: Tx, company_id: str, start: date, end: date, facility_id: str | None = None) -> dict:
    multiplier = Decimal(
        str((tx.scalar("select params from ref.metrics where key = 'LTIFR'") or {}).get("multiplier", 1000000))
    )
    incidents = tx.all(
        """select i.*, f.name as facility from public.incidents i join public.facilities f on f.id = i.facility_id
           where i.company_id = %s and i.occurred_on between %s and %s and (%s::uuid is null or i.facility_id = %s::uuid)
           order by i.occurred_on desc""",
        (company_id, start, end, facility_id, facility_id),
    )
    lab = labour(tx, company_id, start, end, facility_id)
    hours = lab["hours_worked"]
    injuries = [i for i in incidents if i["type"] in ("injury", "fatality")]
    lti = [i for i in injuries if i["lost_time"]]
    by_type: dict[str, int] = {}
    for i in incidents:
        by_type[i["type"]] = by_type.get(i["type"], 0) + 1
    trend = []
    hours_by_month = {}
    rows = tx.all(
        """select to_char(month, 'YYYY-MM') as m, sum(coalesce(working_hours, 0) + coalesce(overtime_hours, 0)) as h,
                  bool_and(working_hours is not null) as known
           from public.labour_monthly where company_id = %s and month between %s and %s
             and (%s::uuid is null or facility_id = %s::uuid) group by 1""",
        (company_id, date(start.year, start.month, 1), end, facility_id, facility_id),
    )
    for r in rows:
        hours_by_month[r["m"]] = Decimal(r["h"]) if r["known"] else None
    for m in lab["months"]:
        mi = [i for i in incidents if i["occurred_on"].strftime("%Y-%m") == m]
        m_lti = sum(1 for i in mi if i["type"] in ("injury", "fatality") and i["lost_time"])
        h = hours_by_month.get(m)
        complete = next((x["complete"] for x in lab["monthly"] if x["month"] == m), False)
        trend.append(
            {
                "month": m,
                "incidents": len(mi),
                "lti": m_lti,
                "ltifr": ddiv(Decimal(m_lti) * multiplier, h) if h and complete else None,
            }
        )
    return {
        "incidents": incidents,
        "by_type": by_type,
        "lti_count": len(lti),
        "fatalities": sum(i["fatalities"] for i in incidents),
        "lost_days": sum(i["lost_days"] for i in incidents),
        "hours_worked": hours,
        "multiplier": multiplier,
        "ltifr": ddiv(Decimal(len(lti)) * multiplier, hours) if hours else None,
        "injury_rate": ddiv(Decimal(len(injuries)) * multiplier, hours) if hours else None,
        "hours_missing": lab["missing"],
        "trend": trend,
    }
