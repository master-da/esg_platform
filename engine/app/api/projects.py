"""Projects (PRD Feature 3): reporting periods moving DRAFT -> DATA_COLLECTION -> REVIEW -> APPROVED -> LOCKED."""

from __future__ import annotations

from datetime import date
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.auth import require_approve, require_read, require_write, user_tx
from app.calc.service import recalculate_project
from app.db import Tx
from app.services.coverage import coverage

router = APIRouter(tags=["projects"])

Stage = Literal["DRAFT", "DATA_COLLECTION", "REVIEW", "APPROVED", "LOCKED"]

# (from, to) -> permission needed
TRANSITIONS: dict[tuple[str, str], str] = {
    ("DRAFT", "DATA_COLLECTION"): "write",
    ("DATA_COLLECTION", "REVIEW"): "write",
    ("REVIEW", "DATA_COLLECTION"): "write",
    ("REVIEW", "APPROVED"): "approve",
    ("APPROVED", "REVIEW"): "approve",
    ("APPROVED", "LOCKED"): "approve",
}


def get_project(tx: Tx, project_id: str) -> dict:
    """Load a project the caller can see (RLS). 404 for other tenants' projects."""
    p = tx.one("select * from public.projects where id = %s", (project_id,))
    if not p:
        raise HTTPException(404, "Project not found")
    return p


class ProjectIn(BaseModel):
    company_id: str
    name: str = Field(min_length=2)
    period_type: Literal["year", "half_year", "quarter"]
    start_date: date
    end_date: date
    boundary: Literal["organization", "division"] = "organization"
    division_name: str | None = None
    upload_deadline: date | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date must not be before the start date")
        if self.boundary == "division" and not (self.division_name or "").strip():
            raise ValueError("Name the division for a division-level project")
        return self


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, tx: Tx = Depends(user_tx)):
    require_write(tx, body.company_id)
    try:
        with tx.privileged():
            with tx.conn.transaction():
                pid = tx.scalar(
                    """insert into public.projects (company_id, name, period_type, start_date, end_date, boundary,
                         division_name, upload_deadline) values (%s, %s, %s, %s, %s, %s, %s, %s) returning id""",
                    (
                        body.company_id,
                        body.name.strip(),
                        body.period_type,
                        body.start_date,
                        body.end_date,
                        body.boundary,
                        body.division_name,
                        body.upload_deadline,
                    ),
                )
    except psycopg.errors.ExclusionViolation:
        clash = tx.one(
            """select name, start_date, end_date from public.projects where company_id = %s and boundary = %s
                 and daterange(start_date, end_date, '[]') && daterange(%s, %s, '[]') limit 1""",
            (body.company_id, body.boundary, body.start_date, body.end_date),
        )
        raise HTTPException(
            409,
            f'The period overlaps project "{clash["name"]}" ({clash["start_date"]} to '
            f"{clash['end_date']}). Projects with the same boundary cannot overlap, so no "
            "emissions are counted twice.",
        ) from None
    with tx.privileged():
        vid = tx.scalar(
            """insert into public.calculation_versions (company_id, project_id, version_no, reason)
               values (%s, %s, 1, 'Initial version') returning id""",
            (body.company_id, pid),
        )
        tx.execute("update public.projects set current_version_id = %s where id = %s", (vid, pid))
        # Every category is listed. One whose template is not available yet starts as not applicable,
        # with the reason shown, so it is visible in the project and in the report's boundary section.
        tx.execute(
            """insert into public.project_categories (company_id, project_id, terminal_key, in_scope, na_reason)
               select %s, %s, key, enabled, case when enabled then null else coalesce(disabled_reason, 'Not available yet') end
               from ref.terminals""",
            (body.company_id, pid),
        )
    return {"id": str(pid)}


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    upload_deadline: date | None = None


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectPatch, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    require_write(tx, str(p["company_id"]))
    fields = body.model_dump(exclude_unset=True)
    if fields:
        with tx.privileged():
            tx.execute(
                f"update public.projects set {', '.join(f'{k} = %({k})s' for k in fields)} where id = %(id)s",
                {**fields, "id": project_id},
            )
    return {"updated": bool(fields)}


def category_rollup(tx: Tx, project_id: str) -> list[dict]:
    """Per-category status for the project detail page and progress bar."""
    rows = tx.all(
        """select pc.terminal_key, pc.in_scope, pc.na_reason, pc.assignee_id, p.full_name as assignee_name,
                  t.name, t.scope, t.category_no, t.module, t.enabled, t.disabled_reason, t.sort, t.accepts_bills,
                  (select count(*) from public.tasks k where k.project_id = pc.project_id
                     and k.terminal_key = pc.terminal_key and k.status = 'open') as open_tasks
           from public.project_categories pc
           join ref.terminals t on t.key = pc.terminal_key
           left join public.profiles p on p.user_id = pc.assignee_id
           where pc.project_id = %s order by t.sort""",
        (project_id,),
    )
    files = tx.all("select terminal_key, status from public.v_file_status where project_id = %s", (project_id,))
    recs = tx.all(
        """select r.terminal_key, count(*) as records,
                  count(cc.*) filter (where cc.status = 'CALCULATED') as calculated,
                  sum(cc.co2e_t) filter (where cc.status = 'CALCULATED') as co2e_t
           from public.activity_records r
           left join public.v_current_calcs cc on cc.activity_record_id = r.id
           where r.project_id = %s and r.deleted_at is null group by r.terminal_key""",
        (project_id,),
    )
    needs = tx.all(
        """select c.terminal_key, count(*) as n from public.categorizations c
           where c.project_id = %s and c.status <> 'ACCEPTED'
             and exists (select 1 from public.activity_records r where r.project_id = c.project_id
                         and r.terminal_key = c.terminal_key and r.category_input_key = c.input_key and r.deleted_at is null)
           group by c.terminal_key""",
        (project_id,),
    )
    by_files: dict[str, list[str]] = {}
    for f in files:
        by_files.setdefault(f["terminal_key"], []).append(f["status"])
    rec_map = {r["terminal_key"]: r for r in recs}
    need_map = {r["terminal_key"]: r["n"] for r in needs}
    out = []
    for r in rows:
        statuses = by_files.get(r["terminal_key"], [])
        if not r["in_scope"]:
            status = "NOT_APPLICABLE"
        elif not statuses:
            status = "NO_DATA"
        elif r["module"] != "ghg":
            status = (
                "CONFIRMED"
                if all(s == "CONFIRMED" for s in statuses)
                else ("NEED_ATTENTION" if "NEED_ATTENTION" in statuses else "AWAITING_CONFIRMATION")
            )
        elif "NEED_ATTENTION" in statuses:
            status = "NEED_ATTENTION"
        elif all(s == "CALCULATED" for s in statuses):
            status = "CALCULATED"
        elif all(s in ("CALCULATED", "PRELIMINARY") for s in statuses):
            status = "PRELIMINARY"
        else:
            status = "READY_TO_CATEGORIZE"
        rec = rec_map.get(r["terminal_key"], {})
        out.append(
            {
                **r,
                "status": status,
                "files": len(statuses),
                "records": rec.get("records", 0),
                "calculated": rec.get("calculated", 0),
                "co2e_t": rec.get("co2e_t"),
                "needs_categorization": need_map.get(r["terminal_key"], 0),
                "need_attention_files": statuses.count("NEED_ATTENTION"),
            }
        )
    return out


@router.get("/companies/{company_id}/projects")
def list_projects(company_id: str, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    projects = tx.all("select * from public.projects where company_id = %s order by start_date desc", (company_id,))
    totals = {
        str(r["project_id"]): r
        for r in tx.all(
            """select project_id, sum(co2e_t) filter (where status = 'CALCULATED') as co2e_t,
                  count(*) filter (where status in ('UNKNOWN_FACTOR', 'UNIT_ERROR')) as calc_errors
           from public.v_current_calcs where company_id = %s group by project_id""",
            (company_id,),
        )
    }
    file_status = tx.all(
        """select project_id, status, count(*) as n from public.v_file_status where company_id = %s
           group by project_id, status""",
        (company_id,),
    )
    tasks = {
        str(r["project_id"]): r["n"]
        for r in tx.all(
            "select project_id, count(*) as n from public.tasks where company_id = %s and status = 'open' group by project_id",
            (company_id,),
        )
    }
    fs: dict[str, dict[str, int]] = {}
    for r in file_status:
        fs.setdefault(str(r["project_id"]), {})[r["status"]] = r["n"]
    out = []
    for p in projects:
        pid = str(p["id"])
        counts = fs.get(pid, {})
        if counts.get("NEED_ATTENTION"):
            calc_status = "NEED_ATTENTION"
        elif not counts:
            calc_status = "NO_DATA"
        elif set(counts) <= {"CALCULATED", "CONFIRMED"}:
            calc_status = "CALCULATED"
        elif set(counts) <= {"CALCULATED", "CONFIRMED", "PRELIMINARY"}:
            calc_status = "PRELIMINARY"
        else:
            calc_status = "READY_TO_CATEGORIZE"
        t = totals.get(pid, {})
        out.append(
            {
                **p,
                "co2e_t": t.get("co2e_t"),
                "calc_status": calc_status,
                "file_status_counts": counts,
                "open_tasks": tasks.get(pid, 0),
            }
        )
    return out


@router.get("/projects/{project_id}")
def project_detail(project_id: str, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    cats = category_rollup(tx, project_id)
    versions = tx.all(
        """select v.id, v.version_no, v.library_as_of, v.reason, v.created_at, v.frozen_at, pr.full_name as created_by_name
           from public.calculation_versions v left join public.profiles pr on pr.user_id = v.created_by
           where v.project_id = %s order by v.version_no desc""",
        (project_id,),
    )
    total = tx.scalar(
        "select sum(co2e_t) from public.v_current_calcs where project_id = %s and status = 'CALCULATED'", (project_id,)
    )
    open_tasks = tx.scalar("select count(*) from public.tasks where project_id = %s and status = 'open'", (project_id,))
    progress: dict[str, int] = {}
    for c in cats:
        # The calculation progress bar counts emission categories only (energy/water rows are confirmed, not calculated).
        if c["module"] == "ghg" and c["status"] not in ("NO_DATA", "NOT_APPLICABLE"):
            progress[c["status"]] = progress.get(c["status"], 0) + 1
    return {
        "project": p,
        "categories": cats,
        "versions": versions,
        "co2e_t": total,
        "open_tasks": open_tasks,
        "progress": progress,
    }


class TransitionIn(BaseModel):
    to: Stage


def _approval_blockers(tx: Tx, project_id: str) -> list[str]:
    blockers = []
    not_calc = tx.all(
        """select f.original_name, f.status, t.name as terminal from public.v_file_status f
           join ref.terminals t on t.key = f.terminal_key
           join public.project_categories pc on pc.project_id = f.project_id and pc.terminal_key = f.terminal_key
           where f.project_id = %s and pc.in_scope and f.status not in ('CALCULATED', 'CONFIRMED') limit 5""",
        (project_id,),
    )
    for f in not_calc:
        blockers.append(f'{f["terminal"]}: "{f["original_name"]}" is {f["status"].replace("_", " ").lower()}')
    unverified = tx.scalar(
        """select count(*) from public.activity_records where project_id = %s and deleted_at is null
           and review_status <> 'USER_VERIFIED'""",
        (project_id,),
    )
    if unverified:
        blockers.append(f"{unverified} activity records are not yet user-verified")
    return blockers


@router.post("/projects/{project_id}/transition")
def transition(project_id: str, body: TransitionIn, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    company = str(p["company_id"])
    need = TRANSITIONS.get((p["stage"], body.to))
    if need is None:
        raise HTTPException(409, f"A project cannot move from {p['stage']} to {body.to}.")
    (require_approve if need == "approve" else require_write)(tx, company)
    if body.to in ("APPROVED", "LOCKED"):
        blockers = _approval_blockers(tx, project_id)
        if blockers:
            raise HTTPException(409, "Not every file is confirmed as Calculated yet: " + "; ".join(blockers))
    with tx.privileged():
        if body.to == "LOCKED":
            tx.execute(
                "update public.calculation_versions set frozen_at = now() where id = %s", (p["current_version_id"],)
            )
            tx.execute(
                "update public.projects set stage = 'LOCKED', locked_at = now(), locked_by = app.uid() where id = %s",
                (project_id,),
            )
        else:
            tx.execute("update public.projects set stage = %s where id = %s", (body.to, project_id))
    action = {"APPROVED": "APPROVE", "LOCKED": "LOCK"}.get(body.to, "STAGE_CHANGE")
    tx.log_event(company, "public.projects", project_id, action, {"from": p["stage"], "to": body.to})
    return {"stage": body.to}


class RecalcIn(BaseModel):
    reason: str = Field(min_length=3)
    confirm: bool = False


@router.post("/projects/{project_id}/recalculate")
def recalculate(project_id: str, body: RecalcIn, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    if p["stage"] == "LOCKED":
        require_approve(tx, str(p["company_id"]))
    else:
        require_write(tx, str(p["company_id"]))
    return recalculate_project(tx, project_id, body.reason, body.confirm)


class CategoryPatch(BaseModel):
    in_scope: bool | None = None
    na_reason: str | None = None
    assignee_id: str | None = None


@router.patch("/projects/{project_id}/categories/{terminal_key}")
def update_category(project_id: str, terminal_key: str, body: CategoryPatch, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    require_write(tx, str(p["company_id"]))
    fields = body.model_dump(exclude_unset=True)
    if fields.get("in_scope") is False and not (fields.get("na_reason") or "").strip():
        raise HTTPException(422, "Give a reason when marking a category as not applicable")
    if fields.get("in_scope"):
        if not tx.scalar("select enabled from ref.terminals where key = %s", (terminal_key,)):
            raise HTTPException(409, "This category has no upload template yet, so it can't be in scope")
        fields["na_reason"] = None
    if fields:
        with tx.privileged():
            tx.execute(
                f"update public.project_categories set {', '.join(f'{k} = %({k})s' for k in fields)} "
                "where project_id = %(p)s and terminal_key = %(t)s",
                {**fields, "p": project_id, "t": terminal_key},
            )
    return {"updated": bool(fields)}


@router.get("/projects/{project_id}/coverage")
def project_coverage(project_id: str, tx: Tx = Depends(user_tx)):
    """Missing months per category and facility (never treated as zero)."""
    return coverage(tx, get_project(tx, project_id))
