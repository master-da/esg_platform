"""Results segment and calculation trail (PRD Feature 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.projects import get_project
from app.auth import user_tx
from app.db import Tx

router = APIRouter(tags=["results"])


@router.get("/projects/{project_id}/results")
def results(project_id: str, tx: Tx = Depends(user_tx)):
    """One table per GHG category: supplier, input, input unit, GHG, GHG unit."""
    get_project(tx, project_id)
    rows = tx.all(
        """select cc.id as calculation_id, cc.terminal_key, t.name as category, t.scope, t.category_no, t.sort,
                  cc.supplier_name, cc.input_quantity, cc.input_unit, cc.co2e_t, cc.status, cc.message,
                  cc.taxonomy_display, cc.quality_grade, fa.name as facility, cc.period_start, cc.period_end
           from public.v_current_calcs cc
           join ref.terminals t on t.key = cc.terminal_key
           join public.facilities fa on fa.id = cc.facility_id
           where cc.project_id = %s
           order by t.sort, cc.supplier_name nulls last, cc.period_start, cc.id""",
        (project_id,),
    )
    categories: dict[str, dict] = {}
    for r in rows:
        cat = categories.setdefault(
            r["terminal_key"],
            {
                "terminal_key": r["terminal_key"],
                "category": r["category"],
                "scope": r["scope"],
                "category_no": r["category_no"],
                "total_t": None,
                "unknown": 0,
                "rows": [],
            },
        )
        cat["rows"].append(r)
        if r["status"] == "CALCULATED":
            cat["total_t"] = (cat["total_t"] or 0) + r["co2e_t"]
        else:
            cat["unknown"] += 1
    return list(categories.values())


@router.get("/calculations/{calc_id}")
def calculation_trail(calc_id: int, tx: Tx = Depends(user_tx)):
    """activity -> factor -> source -> formula -> result, in full. Factor codes only for internal users."""
    c = tx.one(
        """select c.*, r.file_id, r.source_row, r.source_type, r.supplier_name, r.period_start, r.period_end,
                  r.data_basis, r.category_input, r.normalized_quantity, r.normalized_unit, r.review_status,
                  uf.original_name as file_name, fa.name as facility, v.version_no, v.library_as_of, v.frozen_at,
                  t.name as category, t.scope as category_scope, pr.full_name as calculated_by_name
           from public.emission_calculations c
           join public.activity_records r on r.id = c.activity_record_id
           left join public.uploaded_files uf on uf.id = r.file_id
           join public.facilities fa on fa.id = r.facility_id
           join public.calculation_versions v on v.id = c.calc_version_id
           join ref.terminals t on t.key = r.terminal_key
           left join public.profiles pr on pr.user_id = c.calculated_by
           where c.id = %s""",
        (calc_id,),
    )
    if not c:
        raise HTTPException(404, "Calculation not found")
    c["history"] = tx.all(
        """select c2.id, c2.status, c2.co2e_t, c2.calculated_at, v.version_no from public.emission_calculations c2
           join public.calculation_versions v on v.id = c2.calc_version_id
           where c2.activity_record_id = %s order by c2.id desc""",
        (c["activity_record_id"],),
    )
    if c["emission_factor_id"] and tx.scalar("select app.is_internal()"):
        with tx.privileged():
            c["factor_code"] = tx.scalar(
                "select factor_code from lib.emission_factors where id = %s", (c["emission_factor_id"],)
            )
    return c
