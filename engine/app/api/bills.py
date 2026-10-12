"""Invoices & bills - Method 2 (PRD F5): Scope 2 purchased electricity only.

The AI provider proposes values; they are shown in an editable form (status AI_EXTRACTED). Nothing
is saved as an activity record until the user confirms, which creates a USER_VERIFIED record that
then follows the same categorize -> calculate path as template rows.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.ai.provider import get_provider
from app.api.intake import get_file, get_terminal
from app.api.projects import get_project
from app.auth import require_write, user_tx
from app.db import Tx
from app.ingest.parser import ParsedFile
from app.ingest.service import create_records, validation_context
from app.ingest.validation import validate
from app.supabase_admin import storage_signed_url, storage_upload

router = APIRouter(tags=["bills"])

BILL_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
BILL_BASIS = "Utility bill / meter reading"


@router.post("/projects/{project_id}/terminals/{key}/bills", status_code=201)
def upload_bill(project_id: str, key: str, file: UploadFile = File(...), tx: Tx = Depends(user_tx)):
    p = get_project(tx, project_id)
    require_write(tx, str(p["company_id"]))
    t = get_terminal(tx, key)
    if not t.accepts_bills:
        raise HTTPException(409, f"{t.label} accepts its template only; bills are accepted for purchased electricity.")
    if p["stage"] in ("APPROVED", "LOCKED"):
        raise HTTPException(409, f'Project "{p["name"]}" is {p["stage"]}; no new data can be added.')
    media = (file.content_type or "").split(";")[0].strip()
    if media not in BILL_TYPES:
        raise HTTPException(415, "Upload the bill as a PDF or a photo (JPEG, PNG or WebP).")
    data = file.file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Bills must be 10 MB or smaller.")
    file_id = str(uuid.uuid4())
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file.filename or "bill")[-120:]
    path = f"{p['company_id']}/{p['id']}/{t.key}/{file_id}/{safe}"
    storage_upload(path, data, media)

    provider = get_provider()
    extraction = provider.extract_bill(data, media, t.bill_fields)
    status = "AI_EXTRACTED" if provider.available and extraction.document_type else "FAILED"
    with tx.privileged():
        tx.execute(
            """insert into public.uploaded_files (id, company_id, project_id, terminal_key, kind, original_name,
                 storage_path, content_type, size_bytes, sha256, validation_passed, row_count)
               values (%s, %s, %s, %s, 'bill', %s, %s, %s, %s, %s, true, 0)""",
            (
                file_id,
                p["company_id"],
                p["id"],
                t.key,
                file.filename or safe,
                path,
                media,
                len(data),
                hashlib.sha256(data).hexdigest(),
            ),
        )
        tx.execute(
            """insert into public.bill_extractions (company_id, file_id, provider, model, status, document_type,
                 extracted, error) values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)""",
            (
                p["company_id"],
                file_id,
                provider.name,
                provider.model,
                status,
                extraction.document_type,
                json.dumps({"fields": extraction.fields, "confidence": extraction.confidence}),
                extraction.notes,
            ),
        )
    tx.log_event(
        str(p["company_id"]),
        "public.uploaded_files",
        file_id,
        "UPLOAD",
        {"file": file.filename, "terminal": t.key, "kind": "bill", "extraction": status},
    )
    return {"file_id": file_id, "status": status}


@router.get("/files/{file_id}/bill")
def get_bill(file_id: str, tx: Tx = Depends(user_tx)):
    f = get_file(tx, file_id)
    if f["kind"] != "bill":
        raise HTTPException(404, "Not a bill")
    t = get_terminal(tx, f["terminal_key"])
    ex = tx.one("select * from public.bill_extractions where file_id = %s", (file_id,))
    facilities = tx.all(
        "select id, name from public.facilities where company_id = %s order by is_company_level, name",
        (f["company_id"],),
    )
    return {
        "file": {"id": file_id, "name": f["original_name"], "content_type": f["content_type"]},
        "preview_url": storage_signed_url(f["storage_path"], 600),
        # jsonb does not keep key order: present the fields in the template's column order
        "fields": [{"key": c.key, "label": t.bill_fields[c.key]} for c in t.columns if c.key in t.bill_fields],
        "extraction": ex,
        "facilities": facilities,
        "units": next(c.options for c in t.columns if c.key == "unit"),
    }


class BillConfirm(BaseModel):
    facility_id: str
    period_start: date
    period_end: date
    supplier_name: str = Field(min_length=1)
    meter_id: str | None = None
    quantity: Decimal = Field(ge=0)
    unit: str = "kWh"
    amount_billed: Decimal | None = Field(default=None, ge=0)


@router.post("/files/{file_id}/bill/confirm")
def confirm_bill(file_id: str, body: BillConfirm, tx: Tx = Depends(user_tx)):
    f = get_file(tx, file_id)
    if f["kind"] != "bill":
        raise HTTPException(404, "Not a bill")
    require_write(tx, str(f["company_id"]))
    ex = tx.one("select * from public.bill_extractions where file_id = %s", (file_id,))
    if ex["status"] == "USER_VERIFIED":
        raise HTTPException(409, "This bill has already been confirmed.")
    p = get_project(tx, str(f["project_id"]))
    t = get_terminal(tx, f["terminal_key"])
    facility = tx.one(
        "select name from public.facilities where id = %s and company_id = %s", (body.facility_id, f["company_id"])
    )
    if not facility:
        raise HTTPException(422, "Choose one of the company's facilities.")

    # Run the confirmed values through the terminal's own validation rules, exactly like a template row.
    values = {
        "facility": facility["name"],
        "period_start": body.period_start,
        "period_end": body.period_end,
        "supplier_name": body.supplier_name,
        "meter_id": body.meter_id,
        "electricity_type": "Grid electricity",
        "quantity": body.quantity,
        "unit": body.unit,
        "amount_billed": body.amount_billed,
        "data_basis": BILL_BASIS,
        "notes": None,
    }
    raw = {c.header: values.get(c.key) for c in t.columns}
    rows, issues = validate(ParsedFile(meta={}, headers=list(raw), rows=[(1, raw)]), t, validation_context(tx, p))
    if issues:
        raise HTTPException(422, "; ".join(f"{i.field}: {i.problem}" for i in issues))
    created = create_records(tx, p, t, rows, file_id=file_id, source_type="bill_upload", review_status="USER_VERIFIED")
    with tx.privileged():
        tx.execute(
            """update public.bill_extractions set status = 'USER_VERIFIED', confirmed = %s::jsonb,
                 confirmed_by = app.uid(), confirmed_at = now(),
                 activity_record_id = (select id from public.activity_records where file_id = %s limit 1)
               where file_id = %s""",
            (body.model_dump_json(), file_id, file_id),
        )
        tx.execute("update public.uploaded_files set row_count = %s where id = %s", (created, file_id))
    edited = {
        k: v
        for k, v in body.model_dump(mode="json").items()
        if k in (ex["extracted"] or {}).get("fields", {}) and str((ex["extracted"]["fields"] or {}).get(k)) != str(v)
    }
    tx.log_event(
        str(f["company_id"]), "public.bill_extractions", file_id, "CONFIRM_BILL", {"edited_fields": sorted(edited)}
    )
    return {"records_created": created}
