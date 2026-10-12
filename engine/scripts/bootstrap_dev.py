"""LOCAL DEVELOPMENT ONLY: create demo users and companies.

Usage: uv run python -m scripts.bootstrap_dev

Creates internal users, the wireframe's sample company with one user per role, and a
second company used to demonstrate tenant isolation. All passwords: DEV_PASSWORD below.
This is demo *customer* data; no emission factors or regulations are created here.
"""

from __future__ import annotations

from app.db import close_pool, transaction
from app.supabase_admin import create_user

DEV_PASSWORD = "Password123!"

INTERNAL = [
    ("admin@platform.test", "Platform Admin", "PLATFORM_ADMIN", True),
    ("reviewer@platform.test", "Internal Reviewer", "INTERNAL_USER", False),
]

COMPANIES = [
    {
        "legal_name": "Sample Textiles Ltd",
        "trading_name": "Sample Textiles",
        "registration_number": "C-000000",
        "sector_code": "TEXTILES_APPAREL",
        "sub_sector_code": "TEX_GARMENTS",
        "company_size_code": "MEDIUM",
        "crm_record_id": "DEV-0001",
        "district": "Gazipur",
        "city": "Gazipur",
        "facilities": [
            {"name": "Gazipur Factory", "facility_type": "MANUFACTURING", "district": "Gazipur", "city": "Gazipur",
             "environmental_classification": "RED", "employee_count": 1850, "production_type": "Knit garments",
             "production_unit": "pieces"},
            {"name": "Dhaka Head Office", "facility_type": "OFFICE", "district": "Dhaka", "city": "Dhaka",
             "employee_count": 120},
        ],
        "users": [
            ("a.rahman@sample.test", "A. Rahman", "COMPANY_ADMIN"),
            ("s.akter@sample.test", "S. Akter", "SUSTAINABILITY_MANAGER"),
            ("f.manager@sample.test", "F. Manager", "FACILITY_MANAGER"),
            ("t.islam@sample.test", "T. Islam", "DATA_ENTRY"),
            ("auditor@sample.test", "Audit Firm", "AUDITOR"),
            ("viewer@sample.test", "Board Viewer", "VIEWER"),
        ],
    },
    {
        "legal_name": "Other Garments Ltd",
        "trading_name": "Other Garments",
        "sector_code": "TEXTILES_APPAREL",
        "company_size_code": "LARGE",
        "crm_record_id": "DEV-0002",
        "district": "Narayanganj",
        "city": "Narayanganj",
        "facilities": [{"name": "Narayanganj Plant", "facility_type": "MANUFACTURING", "district": "Narayanganj",
                        "city": "Narayanganj", "environmental_classification": "ORANGE"}],
        "users": [("admin@other.test", "Other Admin", "COMPANY_ADMIN")],
    },
]


def _user(tx, email: str, name: str) -> str:
    existing = tx.scalar("select user_id from public.profiles where email = %s", (email,))
    if existing:
        return str(existing)
    return create_user(email, DEV_PASSWORD, name)


def main() -> None:
    with transaction(None) as tx:
        tx.execute("select set_config('app.source', 'dev-bootstrap', true)")
        for email, name, role, lib in INTERNAL:
            uid = _user(tx, email, name)
            tx.execute(
                """insert into public.internal_users (user_id, internal_role, can_edit_library)
                   values (%s, %s, %s) on conflict (user_id) do nothing""", (uid, role, lib))
            print(f"internal  {email:<28} {role}")
        for c in COMPANIES:
            company_id = tx.scalar("select id from public.companies where legal_name = %s", (c["legal_name"],))
            if not company_id:
                fields = {k: v for k, v in c.items() if k not in ("facilities", "users")}
                cols = ", ".join(fields)
                company_id = tx.scalar(
                    f"insert into public.companies ({cols}) values ({', '.join(['%s'] * len(fields))}) returning id",
                    list(fields.values()))
            for f in c["facilities"]:
                cols = ["company_id", *f.keys()]
                tx.execute(
                    f"insert into public.facilities ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
                    "on conflict (company_id, name) do nothing", [company_id, *f.values()])
            for email, name, role in c["users"]:
                uid = _user(tx, email, name)
                tx.execute(
                    """insert into public.memberships (company_id, user_id, role, status)
                       values (%s, %s, %s, 'active') on conflict (company_id, user_id) do nothing""",
                    (company_id, uid, role))
                print(f"{c['legal_name'][:20]:<20} {email:<28} {role}")
    close_pool()
    print(f"\nAll dev users share the password: {DEV_PASSWORD}")


if __name__ == "__main__":
    main()
