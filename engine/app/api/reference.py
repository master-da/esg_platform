"""Reference-data administration for internal library editors (PRD F10, F14): changes are data, not code."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.auth import require_library_editor, user_tx
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
