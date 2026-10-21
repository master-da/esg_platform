"""Create a user with a password you choose, optionally adding them to a company. Sends no email.

Usage: uv run python -m scripts.add_user

For demo accounts and for deployments without an email provider yet. Real users should be invited
from the app (Settings > Users & roles), which lets them set their own password. Needs DATABASE_URL,
SUPABASE_URL and SUPABASE_SECRET_KEY for the target project (environment variables override engine/.env).
"""

from __future__ import annotations

import getpass

from app.config import get_settings
from app.db import close_pool, transaction
from app.supabase_admin import create_user

ROLES = ("COMPANY_ADMIN", "SUSTAINABILITY_MANAGER", "FACILITY_MANAGER", "DATA_ENTRY", "AUDITOR", "VIEWER")


def main() -> None:
    print(f"Target project: {get_settings().supabase_url}")
    try:
        with transaction(None) as tx:
            companies = tx.all("select id, legal_name from public.companies order by legal_name")
            print("  0. No company yet (create the user only; name them as first admin when creating the company)")
            for i, c in enumerate(companies, start=1):
                print(f"  {i}. {c['legal_name']}")
            n = int(input("Company number: "))
            company = companies[n - 1] if n else None
            role = None
            if company:
                for i, r in enumerate(ROLES, start=1):
                    print(f"  {i}. {r}")
                role = ROLES[int(input("Role number: ")) - 1]
            email = input("Email: ").strip().lower()
            name = input("Full name: ").strip()

            tx.execute("select set_config('app.source', 'add-user', true)")
            uid = tx.scalar("select user_id from public.profiles where lower(email) = %s", (email,))
            if not uid:
                password = getpass.getpass("Password (min 12 characters): ")
                if len(password) < 12 or password != getpass.getpass("Repeat password: "):
                    raise SystemExit("Passwords must match and be at least 12 characters.")
                uid = create_user(email, password, name)
            if company:
                tx.execute(
                    """insert into public.memberships (company_id, user_id, role, status)
                       values (%s, %s, %s, 'active')
                       on conflict (company_id, user_id) do update set role = excluded.role, status = 'active'""",
                    (company["id"], uid, role),
                )
    finally:
        close_pool()
    if company:
        print(f"{email} can now sign in to {company['legal_name']} as {role}.")
    else:
        print(f"{email} created. Use it as the first company admin in Settings > Organizations: no email is sent.")


if __name__ == "__main__":
    main()
