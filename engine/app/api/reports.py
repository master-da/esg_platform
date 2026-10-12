"""Export wizard and report generation (PRD F14 C)."""

from __future__ import annotations

import io
import json
import re
from datetime import date
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.projects import get_project
from app.auth import require_read, user_tx
from app.db import Tx
from app.reports import dataset, exports, pdf
from app.reports.wording_guard import WordingViolation

router = APIRouter(tags=["reports"])

Section = Literal[
    "emissions_by_ghg_category",
    "emissions_by_internal_category",
    "energy_water_waste",
    "calculation_trail",
    "assumptions_quality",
]
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


class ExportIn(BaseModel):
    project_id: str
    export_type: str  # "custom", "audit", or any framework key in ref.frameworks (frameworks are data)
    format: Literal["xlsx", "csv", "pdf"]
    period_start: date | None = None
    period_end: date | None = None
    sections: list[Section] = []


def _prepare(tx: Tx, body: ExportIn) -> tuple[dict, dict]:
    p = get_project(tx, body.project_id)
    require_read(tx, str(p["company_id"]))
    start, end = body.period_start or p["start_date"], body.period_end or p["end_date"]
    if start < p["start_date"] or end > p["end_date"] or start > end:
        raise HTTPException(422, f"Choose a period within the project ({p['start_date']} to {p['end_date']}).")
    if body.export_type not in ("custom", "audit") and not tx.scalar(
        "select exists(select 1 from ref.frameworks where key = %s)", (body.export_type,)
    ):
        raise HTTPException(422, f"Unknown export type {body.export_type}")
    if body.export_type == "audit" and body.format == "pdf":
        raise HTTPException(422, "The audit export is produced as Excel or CSV.")
    if body.format == "pdf" and p["stage"] not in ("APPROVED", "LOCKED"):
        raise HTTPException(409, "The PDF report is generated for approved or locked projects only.")
    if body.export_type == "custom" and not body.sections:
        raise HTTPException(422, "Choose at least one data section for a custom export.")
    return p, dataset.build(tx, p, start, end)


@router.post("/exports/preview")
def preview(body: ExportIn, tx: Tx = Depends(user_tx)):
    """Warn about missing or estimated data before anything is exported."""
    _, ds = _prepare(tx, body)
    return {
        "warnings": ds["warnings"],
        "period": ds["period"],
        "rows": len(ds["rows"]),
        "metrics": [{"key": m["key"], "name": m["name"], "status": m["status"]} for m in ds["metrics"]],
    }


@router.post("/exports")
def export(body: ExportIn, tx: Tx = Depends(user_tx)):
    p, ds = _prepare(tx, body)
    try:
        if body.format == "pdf":
            data = pdf.build_pdf(ds)
        elif body.format == "xlsx":
            data = exports.build_xlsx(tx, ds, body.export_type, list(body.sections))
        else:
            data = exports.build_csv(tx, ds, body.export_type, list(body.sections))
    except WordingViolation as exc:
        raise HTTPException(422, str(exc)) from exc
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{ds['company']['legal_name']}_{p['name']}").strip("_")
    name = f"{slug}_{body.export_type}_{ds['period']['start']}_{ds['period']['end']}.{body.format}"
    with tx.privileged():
        tx.execute(
            """insert into public.reports (company_id, project_id, export_type, format, period_start, period_end, params,
                 warnings, calc_version_ids, file_name)
               values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, array[%s]::uuid[], %s)""",
            (
                p["company_id"],
                p["id"],
                body.export_type,
                body.format,
                ds["period"]["start"],
                ds["period"]["end"],
                body.model_dump_json(include={"sections"}),
                json.dumps(ds["warnings"], default=str),
                p["current_version_id"],
                name,
            ),
        )
    tx.log_event(
        str(p["company_id"]),
        "public.reports",
        str(p["id"]),
        "REPORT_GENERATE",
        {"type": body.export_type, "format": body.format, "file": name, "warnings": len(ds["warnings"])},
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type=MEDIA[body.format],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


@router.get("/companies/{company_id}/reports")
def history(company_id: str, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    return tx.all(
        """select r.*, p.name as project_name, pr.full_name as generated_by_name from public.reports r
           left join public.projects p on p.id = r.project_id left join public.profiles pr on pr.user_id = r.generated_by
           where r.company_id = %s order by r.generated_at desc limit 100""",
        (company_id,),
    )
