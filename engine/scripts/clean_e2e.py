"""Remove projects created by the Playwright E2E suite (names starting "E2E " or "Bill ") from the dev DB.

Runs as the database owner with triggers suspended, touching only those test projects.
"""

import psycopg

TABLES = ("emission_calculations", "file_reviews", "bill_extractions", "validation_issues", "categorizations",
          "activity_records", "uploaded_files", "tasks", "notes", "project_categories", "denominators")


def main() -> None:
    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres", autocommit=True) as conn:
        conn.execute("set session_replication_role = replica")
        ids = [r[0] for r in conn.execute(
            "select id from public.projects where name like 'E2E %' or name like 'Bill %'").fetchall()]
        if not ids:
            return
        for t in TABLES:
            col = "file_id" if t in ("validation_issues", "file_reviews", "bill_extractions") else "project_id"
            if col == "file_id":
                conn.execute(f"delete from public.{t} where file_id in (select id from public.uploaded_files "
                             "where project_id = any(%s))", (ids,))
            else:
                conn.execute(f"delete from public.{t} where project_id = any(%s)", (ids,))
        conn.execute("update public.projects set current_version_id = null where id = any(%s)", (ids,))
        conn.execute("delete from public.calculation_versions where project_id = any(%s)", (ids,))
        conn.execute("delete from public.projects where id = any(%s)", (ids,))
        print(f"removed {len(ids)} E2E projects")


if __name__ == "__main__":
    main()
