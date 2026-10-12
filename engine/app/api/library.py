"""Emission Factor Library - internal tool (PRD Feature 6, "Where codes live").

All internal users can view; only library editors (PLATFORM_ADMIN or can_edit_library) can add,
version, activate or retire factors. Every change is audited by the database triggers.
Factor codes are returned ONLY from these internal endpoints.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import psycopg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.auth import require_internal, require_library_editor, user_tx
from app.db import Tx

router = APIRouter(prefix="/library", tags=["library"])

FACTOR_COLS = """f.id, f.factor_code, f.version, f.geography_code, f.activity_unit, f.co2e, f.co2e_co2, f.co2e_ch4,
  f.co2e_n2o, f.gwp_version, f.source_name, f.source_url, f.source_year, f.source_ref, f.methodology,
  f.quality_rating, f.valid_from, f.valid_to, f.status, f.activated_at, f.retired_at, f.advisor_reviewed,
  f.notes, f.created_at"""


@router.get("/tree")
def tree(tx: Tx = Depends(user_tx)):
    require_internal(tx)
    with tx.privileged():
        return tx.all(
            """select n.id, n.code, n.parent_id, n.path::text as path, n.name, n.scope, n.ghg_category, n.is_leaf,
                      n.sort,
                      count(f.id) filter (where f.status = 'active') as active_factors,
                      count(f.id) filter (where f.status = 'draft') as draft_factors
               from lib.taxonomy_nodes n left join lib.emission_factors f on f.taxonomy_node_id = n.id
               group by n.id order by n.path""")


@router.get("/nodes/{node_id}")
def node_detail(node_id: str, tx: Tx = Depends(user_tx)):
    require_internal(tx)
    with tx.privileged():
        node = tx.one(
            """select n.id, n.code, n.path::text as path, n.name, n.scope, n.ghg_category, n.is_leaf,
                      l.display_path
               from lib.taxonomy_nodes n join ref.taxonomy_labels l on l.id = n.id where n.id = %s""", (node_id,))
        if not node:
            raise HTTPException(404, "Node not found")
        factors = tx.all(f"select {FACTOR_COLS} from lib.emission_factors f where f.taxonomy_node_id = %s "
                         "order by f.geography_code, f.version desc", (node_id,))
        conversions = tx.all(
            """select c.id, c.emission_factor_id, c.from_unit, c.to_unit, c.multiplier, c.source_name, c.source_url,
                      c.note from lib.factor_conversions c join lib.emission_factors f on f.id = c.emission_factor_id
               where f.taxonomy_node_id = %s order by c.from_unit""", (node_id,))
    by_factor: dict[str, list] = {}
    for c in conversions:
        by_factor.setdefault(str(c["emission_factor_id"]), []).append(c)
    for f in factors:
        f["conversions"] = by_factor.get(str(f["id"]), [])
    return {"node": node, "factors": factors}


class FactorIn(BaseModel):
    taxonomy_node_id: str
    geography_code: str
    activity_unit: str
    co2e: Decimal = Field(ge=0)
    co2e_co2: Decimal | None = None
    co2e_ch4: Decimal | None = None
    co2e_n2o: Decimal | None = None
    gwp_version: str = Field(min_length=1)
    source_name: str = Field(min_length=3)
    source_url: str | None = None
    source_year: int
    source_ref: str | None = None
    methodology: str | None = None
    quality_rating: str | None = None
    valid_from: date
    valid_to: date
    notes: str | None = None

    @field_validator("valid_to")
    @classmethod
    def _range(cls, v, info):
        if "valid_from" in info.data and v < info.data["valid_from"]:
            raise ValueError("valid_to must not be before valid_from")
        return v


def _factor(tx: Tx, factor_id: str) -> dict:
    with tx.privileged():
        row = tx.one(f"select {FACTOR_COLS}, f.taxonomy_node_id from lib.emission_factors f where f.id = %s",
                     (factor_id,))
    if not row:
        raise HTTPException(404, "Factor not found")
    return row


@router.post("/factors", status_code=201)
def create_factor(body: FactorIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    with tx.privileged():
        node = tx.one("select code, is_leaf from lib.taxonomy_nodes where id = %s", (body.taxonomy_node_id,))
        if not node or not node["is_leaf"]:
            raise HTTPException(422, "Factors can only be attached to leaf categories")
        code = f"{node['code']}-{body.geography_code}"
        version = (tx.scalar("select max(version) from lib.emission_factors where factor_code = %s", (code,)) or 0) + 1
        data = body.model_dump()
        cols = ["factor_code", "version", *data.keys()]
        row = tx.one(f"insert into lib.emission_factors ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
                     "returning id", [code, version, *data.values()])
    return {"id": str(row["id"]), "factor_code": code, "version": version}


@router.patch("/factors/{factor_id}")
def update_draft(factor_id: str, body: FactorIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    if _factor(tx, factor_id)["status"] != "draft":
        raise HTTPException(409, "Only draft factors can be edited. Create a new version instead.")
    data = body.model_dump(exclude={"taxonomy_node_id"})
    with tx.privileged():
        tx.execute(f"update lib.emission_factors set {', '.join(f'{k} = %({k})s' for k in data)} where id = %(id)s",
                   {**data, "id": factor_id})
    return {"updated": True}


@router.delete("/factors/{factor_id}")
def delete_draft(factor_id: str, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    if _factor(tx, factor_id)["status"] != "draft":
        raise HTTPException(409, "Only draft factors can be deleted. Retire it instead.")
    with tx.privileged():
        tx.execute("delete from lib.emission_factors where id = %s", (factor_id,))
    return {"deleted": True}


@router.post("/factors/{factor_id}/activate")
def activate(factor_id: str, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    f = _factor(tx, factor_id)
    if f["status"] != "draft":
        raise HTTPException(409, f"Factor is already {f['status']}")
    try:
        with tx.conn.transaction():   # savepoint so a constraint violation can be reported cleanly
            with tx.privileged():
                tx.execute("update lib.emission_factors set status = 'active' where id = %s", (factor_id,))
    except psycopg.errors.ExclusionViolation:
        with tx.privileged():
            clash = tx.one(
                """select factor_code, version, valid_from, valid_to from lib.emission_factors
                   where taxonomy_node_id = %s and geography_code = %s and status = 'active'
                     and daterange(valid_from, valid_to, '[]') && daterange(%s, %s, '[]') limit 1""",
                (f["taxonomy_node_id"], f["geography_code"], f["valid_from"], f["valid_to"]))
        raise HTTPException(409, f"Validity overlaps active factor {clash['factor_code']} v{clash['version']} "
                                 f"({clash['valid_from']} to {clash['valid_to']}). Retire it or change this "
                                 "factor's validity period first.") from None
    return {"activated": True}


@router.post("/factors/{factor_id}/retire")
def retire(factor_id: str, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    if _factor(tx, factor_id)["status"] != "active":
        raise HTTPException(409, "Only active factors can be retired")
    with tx.privileged():
        tx.execute("update lib.emission_factors set status = 'retired' where id = %s", (factor_id,))
    return {"retired": True}


@router.post("/factors/{factor_id}/new-version", status_code=201)
def new_version(factor_id: str, tx: Tx = Depends(user_tx)):
    """Copy a factor (and its conversions) as the next draft version, e.g. to correct a value."""
    require_library_editor(tx)
    f = _factor(tx, factor_id)
    with tx.privileged():
        version = tx.scalar("select max(version) + 1 from lib.emission_factors where factor_code = %s",
                            (f["factor_code"],))
        new_id = tx.scalar(
            """insert into lib.emission_factors (factor_code, version, taxonomy_node_id, geography_code, activity_unit,
                 co2e, co2e_co2, co2e_ch4, co2e_n2o, gwp_version, source_name, source_url, source_year, source_ref,
                 methodology, quality_rating, valid_from, valid_to, notes)
               select factor_code, %s, taxonomy_node_id, geography_code, activity_unit, co2e, co2e_co2, co2e_ch4,
                 co2e_n2o, gwp_version, source_name, source_url, source_year, source_ref, methodology, quality_rating,
                 valid_from, valid_to, notes from lib.emission_factors where id = %s returning id""",
            (version, factor_id))
        tx.execute(
            """insert into lib.factor_conversions (emission_factor_id, from_unit, to_unit, multiplier, source_name,
                 source_url, note)
               select %s, from_unit, to_unit, multiplier, source_name, source_url, note
               from lib.factor_conversions where emission_factor_id = %s""", (new_id, factor_id))
    return {"id": str(new_id), "version": version}


class ReviewIn(BaseModel):
    advisor_reviewed: bool


@router.post("/factors/{factor_id}/review")
def mark_reviewed(factor_id: str, body: ReviewIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    _factor(tx, factor_id)
    with tx.privileged():
        tx.execute("update lib.emission_factors set advisor_reviewed = %s where id = %s",
                   (body.advisor_reviewed, factor_id))
    return {"updated": True}


class ConversionIn(BaseModel):
    from_unit: str
    multiplier: Decimal = Field(gt=0)
    source_name: str = Field(min_length=3)
    source_url: str | None = None
    note: str | None = None


@router.post("/factors/{factor_id}/conversions", status_code=201)
def add_conversion(factor_id: str, body: ConversionIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    f = _factor(tx, factor_id)
    if f["status"] != "draft":
        raise HTTPException(409, "Conversions can only be added to draft factors")
    if body.from_unit == f["activity_unit"]:
        raise HTTPException(422, "The conversion must start from a different unit than the factor's unit")
    with tx.privileged():
        row = tx.one(
            """insert into lib.factor_conversions (emission_factor_id, from_unit, to_unit, multiplier, source_name,
                 source_url, note) values (%s, %s, %s, %s, %s, %s, %s) returning id""",
            (factor_id, body.from_unit, f["activity_unit"], body.multiplier, body.source_name, body.source_url,
             body.note))
    return {"id": str(row["id"])}


@router.delete("/conversions/{conversion_id}")
def delete_conversion(conversion_id: str, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    with tx.privileged():
        tx.execute("delete from lib.factor_conversions where id = %s", (conversion_id,))
    return {"deleted": True}


REQUIRED_IMPORT = ["taxonomy_code", "geography_code", "activity_unit", "co2e", "gwp_version", "source_name",
                   "source_year", "valid_from", "valid_to"]


@router.post("/import")
def import_csv(file: UploadFile = File(...), tx: Tx = Depends(user_tx)):
    """Bulk-create DRAFT factors from a CSV with the same columns as reference-data/lib/emission_factors.csv.
    Drafts are reviewed and activated individually; nothing becomes active through an import."""
    require_library_editor(tx)
    text = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(line for line in io.StringIO(text) if not line.startswith("#"))
    missing = [c for c in REQUIRED_IMPORT if c not in (reader.fieldnames or [])]
    if missing:
        raise HTTPException(422, f"Missing columns: {', '.join(missing)}")
    created, errors = 0, []
    for i, row in enumerate(reader, start=2):
        empty = [c for c in REQUIRED_IMPORT if not (row.get(c) or "").strip()]
        if empty:
            errors.append(f"Row {i}: missing {', '.join(empty)}")
            continue
        with tx.privileged():
            node = tx.one("select id, code, is_leaf from lib.taxonomy_nodes where code = %s", (row["taxonomy_code"],))
        if not node or not node["is_leaf"]:
            errors.append(f"Row {i}: taxonomy_code {row['taxonomy_code']} is not a leaf category")
            continue
        try:
            fields = {k: (v or None) for k, v in row.items() if k in FactorIn.model_fields and k != "taxonomy_node_id"}
            body = FactorIn(taxonomy_node_id=str(node["id"]), **fields)
        except ValueError as exc:
            errors.append(f"Row {i}: {exc}")
            continue
        try:
            with tx.conn.transaction():
                create_factor(body, tx)
            created += 1
        except (HTTPException, psycopg.Error) as exc:
            errors.append(f"Row {i}: {getattr(exc, 'detail', None) or exc}")
    tx.log_event(None, "lib.emission_factors", None, "IMPORT", {"file": file.filename, "created": created,
                                                                 "errors": len(errors)})
    return {"created": created, "errors": errors}
