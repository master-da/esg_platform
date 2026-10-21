"""Create the first platform admin on a new (e.g. production) deployment.

Usage: uv run python -m scripts.create_admin

Prompts for email, name and password; nothing is hard-coded. Needs DATABASE_URL, SUPABASE_URL and
SUPABASE_SECRET_KEY for the target project (environment variables override engine/.env).
Further users are then invited from the app (Settings > Users & roles, Settings > Organizations).
"""

from __future__ import annotations

import getpass

from app.config import get_settings
from app.db import close_pool, transaction
from app.supabase_admin import create_user


def main() -> None:
    print(f"Target project: {get_settings().supabase_url}")
    email = input("Admin email: ").strip().lower()
    name = input("Full name: ").strip()
    password = getpass.getpass("Password (min 12 characters): ")
    if len(password) < 12 or password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords must match and be at least 12 characters.")
    with transaction(None) as tx:
        tx.execute("select set_config('app.source', 'create-admin', true)")
        uid = tx.scalar("select user_id from public.profiles where lower(email) = %s", (email,))
        if not uid:
            uid = create_user(email, password, name)
        tx.execute(
            """insert into public.internal_users (user_id, internal_role, can_edit_library)
               values (%s, 'PLATFORM_ADMIN', true)
               on conflict (user_id) do update set internal_role = 'PLATFORM_ADMIN', can_edit_library = true""",
            (uid,),
        )
    close_pool()
    print(f"{email} is now a platform admin.")


if __name__ == "__main__":
    main()
