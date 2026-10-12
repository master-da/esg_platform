"""Settings > Organizations (internal) and Settings > Users & Roles (Feature 2).

Membership and internal-user changes have no client write path; they go through here.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.auth import require_internal, require_platform_admin, require_user_admin, user_tx
from app.db import Tx
from app.supabase_admin import invite_user

router = APIRouter(tags=["users"])

# Syntax check only; the invitation email itself proves the address works.
EmailStr = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
                                            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)]

ExternalRole = Literal["COMPANY_ADMIN", "SUSTAINABILITY_MANAGER", "FACILITY_MANAGER", "DATA_ENTRY",
                       "AUDITOR", "VIEWER"]


class OrganizationIn(BaseModel):
    legal_name: str = Field(min_length=2)
    org_category: str = "customer"
    license_tier: str | None = None
    sector_classification_code: str | None = None
    crm_record_id: str | None = None
    tax_vat_number: str | None = None
    first_admin_email: EmailStr
    first_admin_name: str | None = None


class OrganizationPatch(BaseModel):
    org_category: str | None = None
    license_tier: str | None = None
    sector_classification_code: str | None = None
    crm_record_id: str | None = None
    tax_vat_number: str | None = None


@router.post("/admin/organizations", status_code=201)
def create_organization(body: OrganizationIn, tx: Tx = Depends(user_tx)):
    require_internal(tx)
    requires_crm = tx.scalar("select requires_crm_record from ref.org_categories where code = %s",
                             (body.org_category,))
    if requires_crm is None:
        raise HTTPException(422, f"Unknown organization category '{body.org_category}'")
    if requires_crm and not (body.crm_record_id or "").strip():
        raise HTTPException(422, "CRM record ID is required for this organization category")
    with tx.privileged():
        company = tx.one(
            """insert into public.companies (legal_name, org_category, license_tier, sector_classification_code,
                                             crm_record_id, tax_vat_number)
               values (%s, %s, %s, %s, %s, %s) returning id""",
            (body.legal_name.strip(), body.org_category, body.license_tier, body.sector_classification_code,
             body.crm_record_id, body.tax_vat_number),
        )
        user_id, sent = invite_user(tx, body.first_admin_email, body.first_admin_name)
        tx.execute(
            """insert into public.memberships (company_id, user_id, role, status, invited_by)
               values (%s, %s, 'COMPANY_ADMIN', %s, auth.uid())""",
            (company["id"], user_id, "invited" if sent else "active"),
        )
    return {"id": str(company["id"]), "invitation_sent": sent}


@router.patch("/admin/organizations/{company_id}")
def update_organization(company_id: str, body: OrganizationPatch, tx: Tx = Depends(user_tx)):
    require_internal(tx)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"updated": False}
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    with tx.privileged():
        row = tx.one(f"update public.companies set {sets} where id = %(id)s returning id", {**fields, "id": company_id})
    if not row:
        raise HTTPException(404, "Organization not found")
    return {"updated": True}


class InviteIn(BaseModel):
    email: EmailStr
    role: ExternalRole
    full_name: str | None = None


@router.post("/companies/{company_id}/invitations", status_code=201)
def invite_company_user(company_id: str, body: InviteIn, tx: Tx = Depends(user_tx)):
    require_user_admin(tx, company_id)
    with tx.privileged():
        if tx.scalar("select exists(select 1 from public.internal_users iu join public.profiles p "
                     "on p.user_id = iu.user_id where lower(p.email) = lower(%s))", (body.email,)):
            raise HTTPException(422, "This email belongs to an internal (platform) user")
        user_id, sent = invite_user(tx, body.email, body.full_name)
        existing = tx.one("select id from public.memberships where company_id = %s and user_id = %s",
                          (company_id, user_id))
        if existing:
            raise HTTPException(409, "This user is already a member of the company")
        row = tx.one(
            """insert into public.memberships (company_id, user_id, role, status, invited_by)
               values (%s, %s, %s, %s, auth.uid()) returning id""",
            (company_id, user_id, body.role, "invited" if sent else "active"),
        )
    return {"membership_id": str(row["id"]), "invitation_sent": sent}


class MembershipPatch(BaseModel):
    role: ExternalRole | None = None
    status: Literal["active", "disabled"] | None = None


@router.patch("/memberships/{membership_id}")
def update_membership(membership_id: str, body: MembershipPatch, tx: Tx = Depends(user_tx)):
    m = tx.one("select id, company_id, user_id, role, status from public.memberships where id = %s",
               (membership_id,))
    if not m:
        raise HTTPException(404, "Membership not found")
    require_user_admin(tx, str(m["company_id"]))
    new_role = body.role or m["role"]
    new_status = body.status or m["status"]
    demotes_admin = m["role"] == "COMPANY_ADMIN" and (new_role != "COMPANY_ADMIN" or new_status != "active")
    with tx.privileged():
        if demotes_admin:
            others = tx.scalar(
                """select count(*) from public.memberships where company_id = %s and role = 'COMPANY_ADMIN'
                   and status = 'active' and id <> %s""", (m["company_id"], membership_id))
            if others == 0:
                raise HTTPException(422, "A company must keep at least one active Company Admin")
        tx.execute("update public.memberships set role = %s, status = %s where id = %s",
                   (new_role, new_status, membership_id))
    return {"updated": True}


class InternalUserIn(BaseModel):
    email: EmailStr
    full_name: str | None = None
    internal_role: Literal["PLATFORM_ADMIN", "INTERNAL_USER"] = "INTERNAL_USER"
    can_edit_library: bool = False


@router.post("/admin/internal-users", status_code=201)
def create_internal_user(body: InternalUserIn, tx: Tx = Depends(user_tx)):
    require_platform_admin(tx)
    with tx.privileged():
        user_id, sent = invite_user(tx, body.email, body.full_name)
        if tx.scalar("select exists(select 1 from public.memberships where user_id = %s)", (user_id,)):
            raise HTTPException(422, "This user is a client (external) user and cannot be made internal")
        tx.execute(
            """insert into public.internal_users (user_id, internal_role, can_edit_library, created_by)
               values (%s, %s, %s, auth.uid())
               on conflict (user_id) do update set internal_role = excluded.internal_role,
                 can_edit_library = excluded.can_edit_library, active = true""",
            (user_id, body.internal_role, body.can_edit_library),
        )
    return {"user_id": user_id, "invitation_sent": sent}


class InternalUserPatch(BaseModel):
    internal_role: Literal["PLATFORM_ADMIN", "INTERNAL_USER"] | None = None
    can_edit_library: bool | None = None
    active: bool | None = None


@router.patch("/admin/internal-users/{user_id}")
def update_internal_user(user_id: str, body: InternalUserPatch, tx: Tx = Depends(user_tx)):
    require_platform_admin(tx)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"updated": False}
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    with tx.privileged():
        row = tx.one(f"update public.internal_users set {sets} where user_id = %(uid)s returning user_id",
                     {**fields, "uid": user_id})
    if not row:
        raise HTTPException(404, "Internal user not found")
    return {"updated": True}
