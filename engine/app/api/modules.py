"""Energy, water, waste, labour and health & safety dashboards (PRD Features 8-13)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends

from app.api.projects import get_project
from app.auth import require_read, user_tx
from app.db import Tx
from app.services import modules

router = APIRouter(tags=["modules"])


@router.get("/projects/{project_id}/energy")
def energy(
    project_id: str,
    denominator: Literal["employees", "production_mass", "production_units", "revenue"] | None = None,
    tx: Tx = Depends(user_tx),
):
    return modules.energy(tx, get_project(tx, project_id), denominator)


@router.get("/projects/{project_id}/water")
def water(project_id: str, tx: Tx = Depends(user_tx)):
    return modules.water(tx, get_project(tx, project_id))


@router.get("/projects/{project_id}/waste")
def waste(project_id: str, tx: Tx = Depends(user_tx)):
    return modules.waste(tx, get_project(tx, project_id))


@router.get("/companies/{company_id}/labour")
def labour(company_id: str, start: date, end: date, facility_id: str | None = None, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    return modules.labour(tx, company_id, start, end, facility_id)


@router.get("/companies/{company_id}/safety")
def safety(company_id: str, start: date, end: date, facility_id: str | None = None, tx: Tx = Depends(user_tx)):
    require_read(tx, company_id)
    return modules.safety(tx, company_id, start, end, facility_id)
