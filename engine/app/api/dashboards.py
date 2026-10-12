"""Home dashboard and Insights (PRD F16)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.api.compliance import permit_alerts, requirements_for
from app.auth import require_read, user_tx
from app.db import Tx
from app.services import carbon, modules
from app.services.carbon import Filters

router = APIRouter(tags=["dashboards"])


def _projects(tx: Tx, company_id: str) -> list[dict]:
    """Organisation-boundary projects: the non-overlapping series used for dashboards and year-on-year."""
    return tx.all(
        """select * from public.projects where company_id = %s and boundary = 'organization'
           order by start_date""",
        (company_id,),
    )


def _select(projects: list[dict], project_id: str | None) -> dict | None:
    if project_id:
        hit = next((p for p in projects if str(p["id"]) == project_id), None)
        if not hit:
            raise HTTPException(404, "Project not found")
        return hit
    return projects[-1] if projects else None


def _sum_months(rows: list[dict], keys: list[str]) -> dict[str, Decimal | None]:
    out = {}
    for r in rows:
        vals = [r[k] for k in keys if r.get(k) is not None]
        out[r["month"]] = sum((Decimal(str(v)) for v in vals), Decimal(0)) if vals else None
    return out


def _waste_monthly(data: dict) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for r in data["records"]:
        m = r["period_start"].strftime("%Y-%m")
        out[m] = out.get(m, Decimal(0)) + Decimal(str(r["quantity_t"]))
    return out


@router.get("/companies/{company_id}/home")
def home(company_id: str, project_id: str | None = None, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    projects = _projects(tx, company_id)
    proj = _select(projects, project_id)
    reqs = requirements_for(tx, company_id)
    applicable = [r for r in reqs if r["applies"]]
    alerts = permit_alerts(tx, company_id)
    compliance = {
        "applicable": len(applicable),
        "needs_review": sum(r["status"] == "NEEDS_REVIEW" for r in applicable),
        "permit_alerts": len(alerts),
        "expired_permits": sum(a["alert"] == "expired" for a in alerts),
    }
    if not proj:
        return {"project": None, "previous": None, "projects": [], "compliance": compliance}
    prev = carbon.previous_project(tx, proj)
    f = Filters([str(proj["id"])])
    pf = Filters([str(prev["id"])]) if prev else None
    energy, water, waste = modules.energy(tx, proj), modules.water(tx, proj), modules.waste(tx, proj)
    penergy = modules.energy(tx, prev) if prev else None
    pwater = modules.water(tx, prev) if prev else None
    pwaste = modules.waste(tx, prev) if prev else None
    e_keys = ["electricity", "heat_steam_cooling", "fuels_stationary", "fuels_mobile", "renewable"]

    def delta(cur, previous):
        return carbon.matched_months_delta(cur, previous) if previous is not None else {"pct": None, "months": 0}

    return {
        "project": proj,
        "previous": prev,
        "projects": [{"id": str(p["id"]), "name": p["name"], "stage": p["stage"]} for p in reversed(projects)],
        "carbon": {
            "total_t": carbon.total(tx, f),
            "by_scope": carbon.breakdown(tx, f, "scope"),
            "unknown": carbon.unknown_count(tx, [str(proj["id"])]),
            "delta": delta(carbon.monthly(tx, f), carbon.monthly(tx, pf) if pf else None),
        },
        "energy": {
            "total_kwh": energy["total_kwh"],
            "renewable_share_pct": energy["renewable_share_pct"],
            "missing_months": energy["missing_months"],
            "delta": delta(
                _sum_months(energy["monthly"], e_keys), _sum_months(penergy["monthly"], e_keys) if penergy else None
            ),
        },
        "water": {
            "withdrawal_m3": water["withdrawal_m3"],
            "delta": delta(
                {m["month"]: m["withdrawal"] for m in water["monthly"]},
                {m["month"]: m["withdrawal"] for m in pwater["monthly"]} if pwater else None,
            ),
        },
        "waste": {
            "total_t": waste["total_t"],
            "recycling_rate_pct": waste["recycling_rate_pct"],
            "hazardous_t": waste["hazardous_t"],
            "delta": delta(_waste_monthly(waste), _waste_monthly(pwaste) if pwaste else None),
        },
        "compliance": compliance,
    }


@router.get("/companies/{company_id}/insights")
def insights(
    company_id: str,
    project_id: str | None = None,
    facility_id: str | None = None,
    grade: str | None = None,
    path: str | None = None,
    tx: Tx = Depends(user_tx),
):
    require_read(tx, company_id)
    projects = _projects(tx, company_id)
    proj = _select(projects, project_id)
    if not proj:
        return {"project": None, "projects": []}
    prev = carbon.previous_project(tx, proj)
    pid = str(proj["id"])

    def flt(project: str, scope: int | None = None) -> Filters:
        return Filters([project], facility_id=facility_id, grade=grade, path=path, scope=scope)

    cards = []
    for s in (1, 2, 3):
        cur = flt(pid, s)
        cards.append(
            {
                "scope": s,
                "total_t": carbon.total(tx, cur),
                "delta": carbon.matched_months_delta(
                    carbon.monthly(tx, cur), carbon.monthly(tx, flt(str(prev["id"]), s))
                )
                if prev
                else {"pct": None, "months": 0},
                "trend": [{"project": p["name"], "total_t": carbon.total(tx, flt(str(p["id"]), s))} for p in projects],
            }
        )
    depth = (path.count(".") + 2) if path else 2
    yearly = []
    for p in projects:
        row = {"project": p["name"], "project_id": str(p["id"])}
        for r in carbon.breakdown(tx, flt(str(p["id"])), "scope"):
            row[r["key"]] = r["co2e_t"]
        yearly.append(row)
    monthly_by_scope: dict[str, dict] = {}
    for s in (1, 2, 3):
        for r in carbon.breakdown(tx, flt(pid, s), "month"):
            monthly_by_scope.setdefault(r["key"], {"month": r["key"]})[f"Scope {s}"] = r["co2e_t"]
    return {
        "project": proj,
        "previous": prev,
        "projects": [{"id": str(p["id"]), "name": p["name"], "stage": p["stage"]} for p in reversed(projects)],
        "total_t": carbon.total(tx, flt(pid)),
        "scope_cards": cards,
        "yearly": yearly,
        "by_source": carbon.breakdown(tx, flt(pid), f"path:{depth}"),
        "by_facility": carbon.breakdown(tx, flt(pid), "facility"),
        "by_grade": carbon.breakdown(tx, flt(pid), "grade"),
        "monthly": sorted(monthly_by_scope.values(), key=lambda r: r["month"]),
        "unknown": carbon.unknown_count(tx, [pid]),
    }


@router.get("/companies/{company_id}/insights/calcs")
def insight_calcs(
    company_id: str,
    project_id: str,
    facility_id: str | None = None,
    grade: str | None = None,
    path: str | None = None,
    scope: int | None = None,
    month: str | None = None,
    tx: Tx = Depends(user_tx),
):
    """The calculations behind any card, bar or slice (click 1); each row opens its trail (click 2)."""
    require_read(tx, company_id)
    proj = tx.one("select id from public.projects where id = %s and company_id = %s", (project_id, company_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    return carbon.drill(
        tx, Filters([project_id], facility_id=facility_id, grade=grade, path=path, scope=scope, month=month)
    )
