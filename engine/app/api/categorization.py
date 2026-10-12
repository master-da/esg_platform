"""Data Categorization tab (PRD F6 step 3). Description paths only - never factor codes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.intake import get_terminal
from app.api.projects import get_project
from app.auth import require_write, user_tx
from app.calc.library import geography_chain
from app.calc.service import calculate_records
from app.categorize import service as categorize
from app.db import Tx

router = APIRouter(tags=["categorization"])


def factor_availability(tx: Tx, node_ids: list[str], chain: list[str], start: date, end: date) -> dict[str, str]:
    """How a node's factor will resolve for this project: country / regional / global / none."""
    if not node_ids:
        return {}
    with tx.privileged():
        rows = tx.all(
            """select taxonomy_node_id, geography_code from lib.emission_factors
               where taxonomy_node_id = any(%s::uuid[]) and status = 'active'
                 and daterange(valid_from, valid_to, '[]') && daterange(%s, %s, '[]')""",
            (node_ids, start, end),
        )
    geos: dict[str, set[str]] = {}
    for r in rows:
        geos.setdefault(str(r["taxonomy_node_id"]), set()).add(r["geography_code"])
    out = {}
    for nid in node_ids:
        have = geos.get(nid, set())
        level = next((i for i, g in enumerate(chain) if g in have), None)
        if level is None:
            out[nid] = "none"
        elif level == 0:
            out[nid] = "country"
        elif chain[level] == "GLOBAL":
            out[nid] = "global"
        else:
            out[nid] = "regional"
    return out


@router.get("/projects/{project_id}/terminals/{key}/categorizations")
def list_categorizations(project_id: str, key: str, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    rows = tx.all(
        """select c.id, c.input_display, c.status, c.suggested_by, c.suggestion_note, c.suggested_at, c.accepted_at,
                  c.factor_requested_at, c.suggested_node_id, c.accepted_node_id,
                  sl.display_path as suggested_path, al.display_path as accepted_path,
                  pa.full_name as accepted_by_name,
                  count(r.id) as records,
                  array_agg(distinct uf.original_name) filter (where uf.original_name is not null) as files
           from public.categorizations c
           join public.activity_records r on r.project_id = c.project_id and r.terminal_key = c.terminal_key
                and r.category_input_key = c.input_key and r.deleted_at is null
           left join public.uploaded_files uf on uf.id = r.file_id
           left join ref.taxonomy_labels sl on sl.id = c.suggested_node_id
           left join ref.taxonomy_labels al on al.id = c.accepted_node_id
           left join public.profiles pa on pa.user_id = c.accepted_by
           where c.project_id = %s and c.terminal_key = %s
           group by c.id, sl.display_path, al.display_path, pa.full_name
           order by c.status = 'ACCEPTED', c.input_key""",
        (project_id, key),
    )
    country = tx.scalar("select country_code from public.companies where id = %s", (p["company_id"],))
    chain = geography_chain(tx, country)
    nodes = sorted({str(n) for r in rows for n in (r["accepted_node_id"] or r["suggested_node_id"],) if n})
    avail = factor_availability(tx, nodes, chain, p["start_date"], p["end_date"])
    for r in rows:
        nid = r["accepted_node_id"] or r["suggested_node_id"]
        r["factor_availability"] = avail.get(str(nid)) if nid else None
    return rows


@router.get("/projects/{project_id}/terminals/{key}/category-options")
def category_options(project_id: str, key: str, tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    t = get_terminal(tx, key)
    opts = categorize.leaf_options(tx, t)
    chain = geography_chain(
        tx, tx.scalar("select country_code from public.companies where id = %s", (p["company_id"],))
    )
    avail = factor_availability(tx, [str(o["id"]) for o in opts], chain, p["start_date"], p["end_date"])
    return [
        {
            "id": str(o["id"]),
            "display_path": o["display_path"],
            "name": o["name"],
            "factor_availability": avail.get(str(o["id"])),
        }
        for o in opts
    ]


class AcceptIn(BaseModel):
    node_id: str | None = None


def _cat(tx: Tx, cat_id: str) -> dict:
    c = tx.one("select * from public.categorizations where id = %s", (cat_id,))
    if not c:
        raise HTTPException(404, "Categorization not found")
    return c


@router.post("/categorizations/{cat_id}/accept")
def accept(cat_id: str, body: AcceptIn, tx: Tx = Depends(user_tx)):
    """A person accepts the suggestion (or picks another category). Only then is anything calculated."""
    c = _cat(tx, cat_id)
    p = get_project(tx, str(c["project_id"]))
    require_write(tx, str(p["company_id"]))
    t = get_terminal(tx, c["terminal_key"])
    node = body.node_id or (str(c["suggested_node_id"]) if c["suggested_node_id"] else None)
    if not node:
        raise HTTPException(422, "There is no suggestion to accept. Choose a category first.")
    categorize.assert_in_subtree(tx, t, node)
    categorize.accept(tx, [cat_id], {cat_id: node})
    counts = calculate_records(tx, p, categorization_ids=[cat_id])
    return {"accepted": 1, **counts}


@router.post("/projects/{project_id}/terminals/{key}/categorizations/accept-suggested")
def accept_all_suggested(project_id: str, key: str, tx: Tx = Depends(user_tx)):
    """'Accept all suggested' still records the accepting user and time on every row (PRD F6)."""
    p = get_project(tx, project_id)
    require_write(tx, str(p["company_id"]))
    ids = [
        str(r["id"])
        for r in tx.all(
            """select id from public.categorizations where project_id = %s and terminal_key = %s and status = 'SUGGESTED'""",
            (project_id, key),
        )
    ]
    if not ids:
        return {"accepted": 0}
    accepted = categorize.accept(tx, ids, {})
    counts = calculate_records(tx, p, categorization_ids=accepted)
    tx.log_event(
        str(p["company_id"]),
        "public.categorizations",
        None,
        "ACCEPT_ALL_SUGGESTED",
        {"terminal": key, "accepted": len(accepted)},
    )
    return {"accepted": len(accepted), **counts}


@router.post("/categorizations/{cat_id}/request-factor")
def request_factor(cat_id: str, tx: Tx = Depends(user_tx)):
    """Ask the library team for a factor (creates an internal task)."""
    c = _cat(tx, cat_id)
    p = get_project(tx, str(c["project_id"]))
    require_write(tx, str(p["company_id"]))
    t = get_terminal(tx, c["terminal_key"])
    inputs = ", ".join(f"{k}: {v}" for k, v in c["input_display"].items())
    with tx.privileged():
        tx.execute(
            """insert into public.tasks (company_id, project_id, terminal_key, kind, title, description)
               values (%s, %s, %s, 'factor_request', %s, %s)""",
            (
                p["company_id"],
                p["id"],
                t.key,
                f"Factor requested: {t.label}",
                f"No suitable emission factor for [{inputs}] in project {p['name']}.",
            ),
        )
        tx.execute("update public.categorizations set factor_requested_at = now() where id = %s", (cat_id,))
    return {"requested": True}
