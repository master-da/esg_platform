"""Upload handling for a terminal (PRD F5): parse -> detect -> validate -> store -> records."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from decimal import Decimal

from fastapi import HTTPException

from app.calc.library import load_unit_graph
from app.calc.service import calculate_records
from app.calc.units import dmul
from app.categorize import service as categorize
from app.categorize.rules import input_display, input_key
from app.config import get_settings
from app.db import Tx
from app.ingest.parser import ParseError, detect_terminal, parse_file
from app.ingest.terminal import Terminal, load_terminals, norm
from app.ingest.validation import Issue, ValidationContext, validate
from app.supabase_admin import storage_upload


def validation_context(tx: Tx, project: dict) -> ValidationContext:
    facilities = {
        norm(f["name"]): (str(f["id"]), f["name"])
        for f in tx.all("select id, name from public.facilities where company_id = %s", (project["company_id"],))
    }
    units = tx.all("select code, name, dimension from ref.units")
    aliases = {norm(u["code"]): u["code"] for u in units} | {norm(u["name"]): u["code"] for u in units}
    return ValidationContext(
        facilities=facilities,
        unit_dimensions={u["code"]: u["dimension"] for u in units},
        unit_aliases=aliases,
        project_start=project["start_date"],
        project_end=project["end_date"],
    )


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-120:] or "upload"


def grade_for(terminal: Terminal, values: dict) -> str:
    basis_col = terminal.role("data_basis")
    if basis_col and values.get(basis_col.key) in terminal.quality_grades:
        return terminal.quality_grades[values[basis_col.key]]
    return terminal.default_grade or "C"


def normalize(graph, terminal: Terminal, qty: Decimal, unit: str) -> tuple[Decimal, str]:
    """Normalised quantity in the terminal's canonical unit for that dimension (same-dimension only)."""
    target = terminal.canonical_units.get(graph.dimension(unit) or "", unit)
    conv = graph.generic(unit, target)
    if conv is None:
        return qty, unit
    return dmul(qty, conv.multiplier), target


def handle_upload(
    tx: Tx, project: dict, terminal: Terminal, filename: str, data: bytes, content_type: str | None
) -> dict:
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"The file is larger than {settings.max_upload_bytes // (1024 * 1024)} MB.")
    if not terminal.enabled:
        raise HTTPException(409, terminal.disabled_reason or "This category is not accepting uploads yet.")
    if project["stage"] in ("APPROVED", "LOCKED"):
        raise HTTPException(
            409,
            f'Project "{project["name"]}" is {project["stage"]}. '
            + (
                "Its data cannot be changed."
                if project["stage"] == "LOCKED"
                else "Move it back to REVIEW before adding data."
            ),
        )

    issues: list[Issue] = []
    rows = []
    template_version = None
    try:
        parsed = parse_file(filename, data, settings.max_upload_rows)
    except ParseError as exc:
        issues = [Issue(None, None, str(exc), "Download this category's template, fill it in and upload it again")]
        parsed = None
    if parsed is not None:
        terminals = load_terminals(tx)
        detected = detect_terminal(parsed, terminals)
        if detected and detected != terminal.key:
            other = terminals[detected]
            tx.log_event(
                str(project["company_id"]),
                "public.uploaded_files",
                None,
                "UPLOAD_REJECTED",
                {"file": filename, "terminal": terminal.key, "detected": detected},
            )
            raise HTTPException(
                422,
                f'"{filename}" is the {other.label} template, not the {terminal.label} template. '
                f"Upload it on the {other.label} page instead.",
            )
        template_version = parsed.meta.get("template_version")
        rows, issues = validate(parsed, terminal, validation_context(tx, project))

    file_id = str(uuid.uuid4())
    path = f"{project['company_id']}/{project['id']}/{terminal.key}/{file_id}/{_safe_name(filename)}"
    storage_upload(path, data, content_type or "application/octet-stream")
    passed = not any(i.severity == "error" for i in issues)
    with tx.privileged():
        tx.execute(
            """insert into public.uploaded_files (id, company_id, project_id, terminal_key, kind, original_name,
                 storage_path, content_type, size_bytes, sha256, template_version, validation_passed, row_count)
               values (%s, %s, %s, %s, 'template', %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                file_id,
                project["company_id"],
                project["id"],
                terminal.key,
                filename,
                path,
                content_type,
                len(data),
                hashlib.sha256(data).hexdigest(),
                template_version,
                passed,
                len(rows),
            ),
        )
        for i in issues:
            tx.execute(
                """insert into public.validation_issues (company_id, file_id, row_number, field, problem, fix, severity)
                   values (%s, %s, %s, %s, %s, %s, %s)""",
                (project["company_id"], file_id, i.row, i.field, i.problem, i.fix, i.severity),
            )

    created = 0
    if passed:
        created = create_records(tx, project, terminal, rows, file_id=file_id, source_type="template_upload")
    tx.log_event(
        str(project["company_id"]),
        "public.uploaded_files",
        file_id,
        "UPLOAD",
        {
            "file": filename,
            "terminal": terminal.key,
            "rows": len(rows),
            "passed": passed,
            "issues": len(issues),
            "records_created": created,
        },
    )
    return {
        "file_id": file_id,
        "validation_passed": passed,
        "rows": len(rows),
        "issues": len(issues),
        "records_created": created,
    }


def create_records(
    tx: Tx,
    project: dict,
    terminal: Terminal,
    rows,
    *,
    file_id: str | None,
    source_type: str,
    review_status: str = "pending_review",
) -> int:
    """Insert one activity record per validated row (PRD F4) and queue its categorization."""
    graph = load_unit_graph(tx)
    qty_col, unit_col, basis_col = terminal.role("quantity"), terminal.role("unit"), terminal.role("data_basis")
    base_cols = {"facility", "period_start", "period_end", "supplier_name", qty_col.key, unit_col.key}
    inputs: dict[str, dict] = {}
    record_ids = []
    with tx.privileged():
        for row in rows:
            v = row.values
            qty, unit = v[qty_col.key], v[unit_col.key]
            nq, nu = normalize(graph, terminal, qty, unit)
            key = input_key(terminal, v) if terminal.categorization_keys else None
            if key:
                inputs.setdefault(key, input_display(terminal, v))
            attrs = {k: (str(val) if val is not None else None) for k, val in v.items() if k not in base_cols}
            rid = tx.scalar(
                """insert into public.activity_records (company_id, project_id, facility_id, terminal_key, activity_type,
                     file_id, source_row, source_type, supplier_name, period_start, period_end, attributes,
                     category_input_key, category_input, original_quantity, original_unit, normalized_quantity,
                     normalized_unit, data_basis, quality_grade, review_status, verified_by, verified_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s,
                           %s, %s, case when %s = 'USER_VERIFIED' then app.uid() end,
                           case when %s = 'USER_VERIFIED' then now() end)
                   returning id""",
                (
                    project["company_id"],
                    project["id"],
                    v["facility"],
                    terminal.key,
                    terminal.activity_type,
                    file_id,
                    row.source_row,
                    source_type,
                    v.get("supplier_name"),
                    v["period_start"],
                    v["period_end"],
                    _json(attrs),
                    key,
                    _json(input_display(terminal, v)) if key else None,
                    qty,
                    unit,
                    nq,
                    nu,
                    v.get(basis_col.key) if basis_col else None,
                    grade_for(terminal, v),
                    review_status,
                    review_status,
                    review_status,
                ),
            )
            record_ids.append(str(rid))
    if inputs:
        categorize.upsert_inputs(tx, project, terminal, inputs)
        categorize.suggest(tx, project, terminal)
        # Rows whose combination a person already accepted are calculated straight away.
        calculate_records(tx, project, record_ids=record_ids)
    return len(record_ids)


def _json(value) -> str:
    return json.dumps(value, default=str)
