"""Everything a report or export says, assembled in one place (PRD F14 C).

Each metric carries its value, unit, status and the module it came from, so every number in a
generated report traces back to its source. Missing data is reported as missing, never as zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.api.compliance import requirements_for
from app.db import Tx
from app.services import carbon, coverage, modules
from app.services.carbon import Filters


def _metric(key: str, names: dict, value, *, source: str, note: str | None = None, status: str | None = None) -> dict:
    meta = names.get(key, {"name": key, "unit": None})
    return {
        "key": key,
        "name": meta["name"],
        "unit": meta["unit"],
        "value": value,
        "status": status or ("ok" if value is not None else "missing"),
        "source": source,
        "note": note,
    }


def build(tx: Tx, project: dict, period_start: date | None = None, period_end: date | None = None) -> dict:
    pid = str(project["id"])
    start = period_start or project["start_date"]
    end = period_end or project["end_date"]
    full_period = start == project["start_date"] and end == project["end_date"]
    company = tx.one("select * from public.companies where id = %s", (project["company_id"],))
    facilities = tx.all(
        "select name, facility_type, district, city, operational_status, is_company_level "
        "from public.facilities where company_id = %s order by is_company_level, name",
        (project["company_id"],),
    )
    names = {r["key"]: r for r in tx.all("select key, name, unit, params from ref.metrics")}

    rows = tx.all(
        """select cc.*, t.name as category, t.category_no, uf.original_name as file_name, f.name as facility,
                  v.version_no
           from public.v_current_calcs cc join ref.terminals t on t.key = cc.terminal_key
           join public.calculation_versions v on v.id = cc.calc_version_id
           join public.facilities f on f.id = cc.facility_id
           left join public.uploaded_files uf on uf.id = cc.file_id
           where cc.project_id = %s and cc.period_start between %s and %s
           order by t.sort, cc.period_start, cc.id""",
        (pid, start, end),
    )
    calculated = [r for r in rows if r["status"] == "CALCULATED"]
    unknown = [r for r in rows if r["status"] != "CALCULATED"]

    def scope_total(s: int):
        vals = [r["co2e_t"] for r in calculated if r["scope"] == s]
        return sum(vals, Decimal(0)) if vals else None

    categories: dict[str, dict] = {}
    for r in rows:
        c = categories.setdefault(
            r["terminal_key"],
            {
                "category": r["category"],
                "category_no": r["category_no"],
                "scope": r["scope"],
                "co2e_t": None,
                "rows": 0,
                "unknown": 0,
            },
        )
        c["rows"] += 1
        if r["status"] == "CALCULATED":
            c["co2e_t"] = (c["co2e_t"] or Decimal(0)) + r["co2e_t"]
        else:
            c["unknown"] += 1
    by_path = carbon.breakdown(tx, Filters([pid]), "path:3")

    energy, water, waste = (
        modules.energy(tx, project, "production_mass"),
        modules.water(tx, project),
        modules.waste(tx, project),
    )
    labour = modules.labour(tx, str(project["company_id"]), start, end)
    safety = modules.safety(tx, str(project["company_id"]), start, end)
    module_note = None if full_period else "Module figures cover the full project period"
    s1, s2, s3 = scope_total(1), scope_total(2), scope_total(3)
    ghg_note = f"{len(unknown)} rows without a factor are excluded (UNKNOWN), not counted as zero" if unknown else None
    metrics = [
        _metric("GHG_SCOPE_1", names, s1, source="Results (calculations, Scope 1)", note=ghg_note),
        _metric("GHG_SCOPE_2", names, s2, source="Results (calculations, Scope 2)", note=ghg_note),
        _metric("GHG_SCOPE_3", names, s3, source="Results (calculations, Scope 3)", note=ghg_note),
        _metric(
            "GHG_TOTAL",
            names,
            sum(v for v in (s1, s2, s3) if v is not None) if any((s1, s2, s3)) else None,
            source="Results (Scopes 1-3)",
            note=ghg_note,
        ),
        _metric(
            "ENERGY_TOTAL",
            names,
            energy["total_kwh"],
            source="Energy module",
            note=module_note
            or (f"{len(energy['missing_months'])} months Missing" if energy["missing_months"] else None),
        ),
        _metric(
            "ENERGY_RENEWABLE_SHARE", names, energy["renewable_share_pct"], source="Energy module", note=module_note
        ),
        _metric(
            "ENERGY_INTENSITY",
            names,
            (energy["intensity"] or {}).get("value"),
            source="Energy module",
            note="kWh per tonne of production" + (f"; {module_note}" if module_note else ""),
        ),
        _metric("WATER_WITHDRAWAL", names, water["withdrawal_m3"], source="Water module", note=module_note),
        _metric("WATER_DISCHARGE", names, water["discharge_m3"], source="Water module", note=module_note),
        _metric(
            "WATER_CONSUMPTION", names, water["consumption_m3"], source="Water module", note=water["consumption_basis"]
        ),
        _metric(
            "WASTE_TOTAL", names, waste["total_t"], source="Waste module (Scope 3 category 3.5 data)", note=module_note
        ),
        _metric("WASTE_HAZARDOUS", names, waste["hazardous_t"], source="Waste module", note=module_note),
        _metric("WASTE_RECYCLED", names, waste["recycled_t"], source="Waste module", note=module_note),
        _metric(
            "WASTE_RECYCLING_RATE",
            names,
            waste["recycling_rate_pct"],
            source="Waste module",
            note=waste["recycling_definition"],
        ),
        _metric("HEADCOUNT_AVG", names, labour["headcount_avg"], source="Labour module"),
        _metric("NEW_HIRES", names, labour["new_hires"], source="Labour module"),
        _metric("TURNOVER_RATE", names, labour["turnover_rate_pct"], source="Labour module"),
        _metric("TRAINING_HOURS_PER_EMPLOYEE", names, labour["training_hours_per_employee"], source="Labour module"),
        _metric("HOURS_WORKED", names, labour["hours_worked"], source="Labour module"),
        _metric("LTI_COUNT", names, safety["lti_count"], source="Health & safety module"),
        _metric(
            "LTIFR",
            names,
            safety["ltifr"],
            source="Health & safety module",
            note=f"per {int(safety['multiplier']):,} hours worked",
        ),
        _metric(
            "INJURY_RATE",
            names,
            safety["injury_rate"],
            source="Health & safety module",
            note=f"per {int(safety['multiplier']):,} hours worked",
        ),
        _metric("FATALITIES", names, safety["fatalities"], source="Health & safety module"),
        _metric("LOST_DAYS", names, safety["lost_days"], source="Health & safety module"),
    ]

    factor_ids = sorted({str(r["emission_factor_id"]) for r in calculated if r["emission_factor_id"]})
    review = {}
    if factor_ids:
        with tx.privileged():
            review = {
                str(r["id"]): r["advisor_reviewed"]
                for r in tx.all(
                    "select id, advisor_reviewed from lib.emission_factors where id = any(%s::uuid[])", (factor_ids,)
                )
            }
    sources: dict[tuple, dict] = {}
    for r in calculated:
        k = (r["factor_source_name"], r["factor_source_year"], r["gwp_version"])
        s = sources.setdefault(
            k,
            {
                "source": r["factor_source_name"],
                "year": r["factor_source_year"],
                "gwp": r["gwp_version"],
                "url": r["factor_source_url"],
                "rows": 0,
                "pending_advisor_review": False,
            },
        )
        s["rows"] += 1
        s["pending_advisor_review"] |= not review.get(str(r["emission_factor_id"]), False)

    total_t = sum((r["co2e_t"] for r in calculated), Decimal(0))
    grades = {}
    for g in ("A", "B", "C"):
        t = sum((r["co2e_t"] for r in calculated if r["quality_grade"] == g), Decimal(0))
        grades[g] = {"co2e_t": t, "share_pct": (t / total_t * 100) if total_t else None}
    pending = tx.scalar(
        """select count(*) from public.activity_records where project_id = %s and deleted_at is null
                           and review_status <> 'USER_VERIFIED'""",
        (pid,),
    )
    gaps = [c for c in coverage.coverage(tx, project) if c["missing_months"]]
    na = tx.all(
        """select t.name, pc.na_reason from public.project_categories pc join ref.terminals t on t.key = pc.terminal_key
                   where pc.project_id = %s and not pc.in_scope order by t.sort""",
        (pid,),
    )
    no_data = tx.all(
        """select t.name from public.project_categories pc join ref.terminals t on t.key = pc.terminal_key
                        where pc.project_id = %s and pc.in_scope and t.enabled and t.module = 'ghg'
                          and not exists (select 1 from public.activity_records r where r.project_id = pc.project_id
                                          and r.terminal_key = pc.terminal_key and r.deleted_at is null)
                        order by t.sort""",
        (pid,),
    )
    assumptions = tx.all(
        """select a.category, a.statement, p.full_name as author, a.created_at from public.assumptions a
                            left join public.profiles p on p.user_id = a.created_by where a.project_id = %s
                            order by a.created_at""",
        (pid,),
    )
    verifications = tx.all("select * from public.verifications where project_id = %s order by statement_date", (pid,))
    versions = tx.all(
        """select v.version_no, v.reason, v.library_as_of, v.created_at, v.frozen_at, p.full_name as created_by
                         from public.calculation_versions v left join public.profiles p on p.user_id = v.created_by
                         where v.project_id = %s order by v.version_no""",
        (pid,),
    )

    system_limitations = [
        "Scope 2 is reported location-based only, using national grid factors.",
        "Where no Bangladesh-specific factor exists, UK DESNZ factors are applied as international defaults.",
    ]
    if any(r["conversion_kind"] == "fx" for r in calculated):
        system_limitations.append(
            "Spend-based figures convert BDT to USD at the cited annual average rate, without "
            "inflation adjustment to the factor's 2022 price year."
        )
    if any(s["pending_advisor_review"] for s in sources.values()):
        system_limitations.append("Some emission factors used are pending review by the domain advisor.")
    if unknown:
        cats = sorted({r["category"] for r in unknown})
        system_limitations.append(
            f"{len(unknown)} rows have no applicable emission factor (UNKNOWN) and are excluded: "
            + ", ".join(cats)
            + "."
        )
    for c in no_data:
        system_limitations.append(f"No data was provided for {c['name']} (Missing).")
    for c in na:
        system_limitations.append(f"{c['name']} was marked not applicable: {c['na_reason']}.")
    if gaps:
        system_limitations.append(
            f"{len(gaps)} category and facility combinations have missing months, shown as Missing."
        )
    if pending:
        system_limitations.append(f"{pending} activity rows are not yet confirmed by a person.")

    warnings = []
    if unknown:
        warnings.append(
            {"level": "error", "text": f"{len(unknown)} rows have no emission factor (UNKNOWN); they are excluded."}
        )
    if gaps:
        warnings.append({"level": "warning", "text": f"Missing months in {len(gaps)} category/facility combinations."})
    if no_data:
        warnings.append({"level": "warning", "text": f"{len(no_data)} in-scope emission categories have no data."})
    if grades["C"]["share_pct"]:
        warnings.append(
            {
                "level": "info",
                "text": f"{grades['C']['share_pct']:.1f}% of calculated emissions are estimated "
                "or default data (grade C).",
            }
        )
    if pending:
        warnings.append({"level": "warning", "text": f"{pending} rows are not yet confirmed by a person."})
    if not full_period:
        warnings.append(
            {
                "level": "info",
                "text": "The selected period is narrower than the project: emissions are filtered "
                "by record period start; module figures cover the whole project.",
            }
        )

    return {
        "company": company,
        "facilities": facilities,
        "project": project,
        "period": {"start": start, "end": end},
        "metrics": metrics,
        "categories": list(categories.values()),
        "by_path": by_path,
        "rows": rows,
        "factor_sources": list(sources.values()),
        "grades": grades,
        "coverage_gaps": gaps,
        "not_applicable": na,
        "no_data": no_data,
        "assumptions": assumptions,
        "limitations": system_limitations,
        "warnings": warnings,
        "verifications": verifications,
        "versions": versions,
        "requirements": [r for r in requirements_for(tx, str(project["company_id"])) if r["applies"]],
        "energy": energy,
        "water": water,
        "waste": waste,
        "labour": labour,
        "safety": safety,
    }
