"""Persisting calculations (PRD Feature 7).

Only calculate_emissions() produces numbers; this module feeds it the inputs and stores the full,
insert-only snapshot in public.emission_calculations. A record's current result is the latest row
in the project's current calculation version (view public.v_current_calcs).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException

from app.calc.engine import ENGINE_VERSION, Activity, calculate_emissions, resolve_factor
from app.calc.library import geography_chain, load_factors, load_fx, load_unit_graph
from app.db import Tx


def _nodes(tx: Tx, node_ids: list[str]) -> dict[str, dict]:
    if not node_ids:
        return {}
    with tx.privileged():
        rows = tx.all(
            """select n.id, n.path::text as path, n.scope, n.ghg_category, l.display_path
               from lib.taxonomy_nodes n join ref.taxonomy_labels l on l.id = n.id
               where n.id = any(%s::uuid[])""",
            (node_ids,),
        )
    return {str(r["id"]): r for r in rows}


def calculate_records(
    tx: Tx,
    project: dict,
    *,
    version_id: str | None = None,
    record_ids: list[str] | None = None,
    categorization_ids: list[str] | None = None,
    terminal_key: str | None = None,
) -> dict:
    """Calculate every active record whose categorization is ACCEPTED (optionally narrowed) into a version."""
    version = tx.one(
        "select * from public.calculation_versions where id = %s", (version_id or project["current_version_id"],)
    )
    filters, params = ["r.project_id = %(p)s", "r.deleted_at is null", "c.status = 'ACCEPTED'"], {"p": project["id"]}
    if record_ids is not None:
        filters.append("r.id = any(%(ids)s::uuid[])")
        params["ids"] = record_ids
    if categorization_ids is not None:
        filters.append("c.id = any(%(cats)s::uuid[])")
        params["cats"] = categorization_ids
    if terminal_key is not None:
        filters.append("r.terminal_key = %(t)s")
        params["t"] = terminal_key
    records = tx.all(
        f"""select r.id, r.company_id, r.original_quantity, r.original_unit, r.period_start, r.period_end,
                   r.quality_grade, r.review_status, c.id as categorization_id, c.accepted_node_id, c.accepted_by
            from public.activity_records r
            join public.categorizations c on c.project_id = r.project_id and c.terminal_key = r.terminal_key
                 and c.input_key = r.category_input_key
            where {" and ".join(filters)}""",
        params,
    )
    if not records:
        return {"calculated": 0, "unknown_factor": 0, "unit_error": 0}

    node_ids = sorted({str(r["accepted_node_id"]) for r in records})
    nodes = _nodes(tx, node_ids)
    factors = load_factors(tx, node_ids)
    graph, fx = load_unit_graph(tx), load_fx(tx)
    country = tx.scalar("select country_code from public.companies where id = %s", (project["company_id"],))
    chain = geography_chain(tx, country)

    counts = {"calculated": 0, "unknown_factor": 0, "unit_error": 0}
    with tx.privileged():
        for r in records:
            node_id = str(r["accepted_node_id"])
            node = nodes[node_id]
            factor = resolve_factor(factors.get(node_id, []), chain, r["period_start"], version["library_as_of"])
            res = calculate_emissions(
                Activity(Decimal(r["original_quantity"]), r["original_unit"], r["period_start"]), factor, graph, fx
            )
            message = res.message
            if res.status == "CALCULATED" and factor and r["period_end"] > factor.valid_to:
                message = (
                    f"The record's period runs past the factor's validity ({factor.valid_to}); the factor "
                    "valid on the period start was applied."
                )
            f, conv = res.factor, res.conversion
            tx.execute(
                """insert into public.emission_calculations (company_id, project_id, calc_version_id, activity_record_id,
                     categorization_id, status, message, taxonomy_node_id, taxonomy_path, taxonomy_display, scope,
                     ghg_category, emission_factor_id, factor_value, factor_unit, factor_geography, factor_source_name,
                     factor_source_url, factor_source_year, factor_version, gwp_version, conversion_from, conversion_to,
                     conversion_multiplier, conversion_kind, conversion_source, input_quantity, input_unit,
                     factor_unit_quantity, co2e_kg, co2_kg, ch4_kg, n2o_kg, quality_grade, formula, engine_version)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s::extensions.ltree, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    r["company_id"],
                    project["id"],
                    version["id"],
                    r["id"],
                    r["categorization_id"],
                    res.status,
                    message,
                    node_id,
                    node["path"],
                    node["display_path"],
                    node["scope"],
                    node["ghg_category"],
                    f.id if f else None,
                    f.co2e if f else None,
                    f.activity_unit if f else None,
                    f.geography_code if f else None,
                    f.source_name if f else None,
                    f.source_url if f else None,
                    f.source_year if f else None,
                    f.version if f else None,
                    f.gwp_version if f else None,
                    conv.from_unit if conv else None,
                    conv.to_unit if conv else None,
                    conv.multiplier if conv else None,
                    conv.kind if conv else None,
                    conv.source if conv else None,
                    r["original_quantity"],
                    r["original_unit"],
                    res.factor_unit_qty,
                    res.co2e_kg,
                    res.co2e_co2_kg,
                    res.co2e_ch4_kg,
                    res.co2e_n2o_kg,
                    r["quality_grade"],
                    res.formula,
                    ENGINE_VERSION,
                ),
            )
            counts[res.status.lower()] += 1
            if r["review_status"] != "USER_VERIFIED":
                # The person who accepted the categorization confirmed how this row is treated (PRD F5).
                tx.execute(
                    """update public.activity_records set review_status = 'USER_VERIFIED', verified_by = %s,
                         verified_at = now() where id = %s""",
                    (r["accepted_by"], r["id"]),
                )
    return counts


def recalculate_project(tx: Tx, project_id: str, reason: str, confirm_locked: bool) -> dict:
    """New calculation version against the library as of now (PRD F3/F7). Old versions are kept."""
    with tx.privileged():
        project = tx.one("select * from public.projects where id = %s for update", (project_id,))
    if project["stage"] == "LOCKED" and not confirm_locked:
        raise HTTPException(
            409,
            "This project is LOCKED. Recalculating creates a new calculation version and keeps "
            "the current one; confirm explicitly to continue.",
        )
    with tx.privileged():
        next_no = tx.scalar(
            "select coalesce(max(version_no), 0) + 1 from public.calculation_versions where project_id = %s",
            (project_id,),
        )
        version_id = tx.scalar(
            """insert into public.calculation_versions (company_id, project_id, version_no, reason, frozen_at)
               values (%s, %s, %s, %s, case when %s then now() end) returning id""",
            (project["company_id"], project_id, next_no, reason, project["stage"] == "LOCKED"),
        )
        counts = calculate_records(tx, project, version_id=str(version_id))
        tx.execute("update public.projects set current_version_id = %s where id = %s", (version_id, project_id))
    tx.log_event(
        str(project["company_id"]),
        "public.projects",
        project_id,
        "RECALCULATE",
        {"version_no": next_no, "reason": reason, **counts},
    )
    return {"version_id": str(version_id), "version_no": next_no, **counts}
