"""Reference-data administration for internal library editors (PRD F10, F14): changes are data, not code."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.auth import require_library_editor, user_tx
from app.compliance.applicability import ConditionError, validate
from app.db import Tx

router = APIRouter(prefix="/reference", tags=["reference"])


class ThresholdIn(BaseModel):
    parameter_key: str
    destination: str | None = None
    sector_code: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    warning_band_pct: Decimal = Field(default=Decimal(10), ge=0, lt=100)
    regulator: str = Field(min_length=2)
    regulation: str = Field(min_length=3)
    source_url: str = Field(min_length=8)
    status: Literal["VERIFIED", "NEEDS_REVIEW"] = "NEEDS_REVIEW"
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _limits(self):
        if self.min_value is None and self.max_value is None:
            raise ValueError("Give a minimum, a maximum, or both")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("The minimum must not exceed the maximum")
        return self


@router.post("/wq-thresholds", status_code=201)
def add_threshold(body: ThresholdIn, tx: Tx = Depends(user_tx)):
    """A new limit (or a new version of one). Earlier versions keep applying to earlier samples."""
    require_library_editor(tx)
    with tx.privileged():
        version = tx.scalar(
            """select coalesce(max(version), 0) + 1 from ref.wq_thresholds where parameter_key = %s
               and destination is not distinct from %s and sector_code is not distinct from %s""",
            (body.parameter_key, body.destination, body.sector_code),
        )
        tid = tx.scalar(
            f"""insert into ref.wq_thresholds ({", ".join(body.model_dump())}, version)
                values ({", ".join(["%s"] * len(body.model_dump()))}, %s) returning id""",
            [*body.model_dump().values(), version],
        )
    return {"id": str(tid), "version": version}


class EndIn(BaseModel):
    valid_to: date


@router.post("/wq-thresholds/{threshold_id}/end")
def end_threshold(threshold_id: str, body: EndIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    with tx.privileged():
        row = tx.one(
            "update ref.wq_thresholds set valid_to = %s where id = %s and valid_from <= %s returning id",
            (body.valid_to, threshold_id, body.valid_to),
        )
    if not row:
        raise HTTPException(404, "Threshold not found, or the end date is before its start")
    return {"ended": True}


# -- Regulatory requirements -----------------------------------------------------------------


class RequirementIn(BaseModel):
    code: str = Field(min_length=3)
    regulator: str = Field(min_length=2)
    law: str = Field(min_length=2)
    title: str = Field(min_length=3)
    description: str | None = None
    frequency: str | None = None
    required_metric_key: str | None = None
    required_document: str | None = None
    source_url: str = Field(pattern=r"^https?://")
    effective_date: date
    effective_until: date | None = None
    applicability_conditions: dict = Field(default_factory=lambda: {"all": []})
    applies_universally: bool = False
    status: Literal["VERIFIED", "NEEDS_REVIEW"] = "NEEDS_REVIEW"
    review_note: str | None = None


@router.post("/requirements", status_code=201)
def save_requirement(body: RequirementIn, tx: Tx = Depends(user_tx)):
    """Adds a requirement, or a new version of an existing code. Earlier versions are kept."""
    require_library_editor(tx)
    try:
        validate(body.applicability_conditions)
    except ConditionError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not body.applies_universally and body.applicability_conditions in ({"all": []}, {}):
        raise HTTPException(
            422, "Give applicability conditions, or mark the requirement as universal only if it truly is."
        )
    data = body.model_dump()
    data["applicability_conditions"] = json.dumps(data["applicability_conditions"])
    with tx.privileged():
        version = tx.scalar(
            "select coalesce(max(version), 0) + 1 from ref.regulatory_requirements where code = %s", (body.code,)
        )
        cols = [*data.keys(), "version"]
        placeholders = ", ".join("%s::jsonb" if c == "applicability_conditions" else "%s" for c in cols)
        rid = tx.scalar(
            f"insert into ref.regulatory_requirements ({', '.join(cols)}) values ({placeholders}) returning id",
            [*data.values(), version],
        )
    return {"id": str(rid), "version": version}


# -- Frameworks, mappings and metric parameters ------------------------------------------------


class FrameworkIn(BaseModel):
    key: str = Field(pattern=r"^[A-Z0-9_]{2,40}$")
    name: str = Field(min_length=2)
    version: str | None = None
    description: str | None = None
    source_url: str | None = None


@router.post("/frameworks", status_code=201)
def add_framework(body: FrameworkIn, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    with tx.privileged():
        tx.execute(
            """insert into ref.frameworks (key, name, version, description, source_url) values (%s, %s, %s, %s, %s)
                      on conflict (key) do update set name = excluded.name, version = excluded.version,
                        description = excluded.description, source_url = excluded.source_url""",
            (body.key, body.name, body.version, body.description, body.source_url),
        )
    return {"saved": True}


class MappingIn(BaseModel):
    framework_key: str
    metric_key: str
    disclosure_ref: str = Field(min_length=1)
    disclosure_title: str | None = None


@router.post("/mappings", status_code=201)
def add_mapping(body: MappingIn, tx: Tx = Depends(user_tx)):
    """A new framework needs only mapping rows: metrics and calculations are reused (PRD F14 B)."""
    require_library_editor(tx)
    with tx.privileged():
        tx.execute(
            """insert into ref.framework_metric_mappings (framework_key, metric_key, disclosure_ref, disclosure_title)
                      values (%s, %s, %s, %s) on conflict do nothing""",
            (body.framework_key, body.metric_key, body.disclosure_ref, body.disclosure_title),
        )
    return {"saved": True}


@router.delete("/mappings")
def delete_mapping(framework_key: str, metric_key: str, disclosure_ref: str, tx: Tx = Depends(user_tx)):
    require_library_editor(tx)
    with tx.privileged():
        tx.execute(
            """delete from ref.framework_metric_mappings where framework_key = %s and metric_key = %s
                      and disclosure_ref = %s""",
            (framework_key, metric_key, disclosure_ref),
        )
    return {"deleted": True}


class MetricParams(BaseModel):
    params: dict


@router.patch("/metrics/{key}")
def update_metric_params(key: str, body: MetricParams, tx: Tx = Depends(user_tx)):
    """e.g. the LTIFR multiplier (1,000,000 or 200,000 hours)."""
    require_library_editor(tx)
    with tx.privileged():
        row = tx.one(
            "update ref.metrics set params = %s::jsonb where key = %s returning key", (json.dumps(body.params), key)
        )
    if not row:
        raise HTTPException(404, "Unknown metric")
    return {"updated": True}
