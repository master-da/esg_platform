"""Regulatory requirements and permits (PRD F14 A, F15)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from app.auth import require_read, user_tx
from app.compliance.applicability import evaluate, fields
from app.db import Tx

router = APIRouter(tags=["compliance"])


def requirements_for(tx: Tx, company_id: str, on: date | None = None) -> list[dict]:
    on = on or date.today()
    company = tx.one("select * from public.companies where id = %s", (company_id,))
    facilities = tx.all(
        "select * from public.facilities where company_id = %s and not is_company_level "
        "and operational_status <> 'closed' order by name",
        (company_id,),
    )
    reqs = tx.all(
        """select distinct on (code) * from ref.regulatory_requirements
           where effective_date <= %s and (effective_until is null or effective_until >= %s)
           order by code, version desc""",
        (on, on),
    )
    out = []
    for r in reqs:
        cond = r["applicability_conditions"]
        facility_level = any(f.startswith("facility.") for f in fields(cond))
        matches = []
        if facility_level:
            for f in facilities:
                ok, why = evaluate(cond, {"company": company, "facility": f})
                if ok:
                    matches.append({"facility_id": str(f["id"]), "facility": f["name"], "because": why})
            applies = bool(matches)
        else:
            applies, why = evaluate(cond, {"company": company})
            if applies:
                matches.append({"facility_id": None, "facility": "Whole company", "because": why})
        out.append(
            {
                **r,
                "applies": applies or r["applies_universally"],
                "applies_to": matches,
                "level": "facility" if facility_level else "company",
            }
        )
    return out


@router.get("/companies/{company_id}/requirements")
def list_requirements(company_id: str, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    return requirements_for(tx, company_id)


def permit_alerts(tx: Tx, company_id: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    rows = tx.all(
        """select p.*, f.name as facility from public.permits p left join public.facilities f on f.id = p.facility_id
           where p.company_id = %s and p.status in ('active', 'renewal_in_progress') and p.expiry_date is not null
           order by p.expiry_date""",
        (company_id,),
    )
    out = []
    for p in rows:
        days = (p["expiry_date"] - today).days
        if p["expiry_date"] < today:
            level = "expired"
        elif p["expiry_date"] <= today + timedelta(days=p["reminder_lead_days"]):
            level = "due"
        else:
            continue
        out.append({**p, "days_to_expiry": days, "alert": level})
    return out


@router.get("/companies/{company_id}/permits/alerts")
def list_permit_alerts(company_id: str, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    return permit_alerts(tx, company_id)
