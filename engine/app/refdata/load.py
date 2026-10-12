"""Load versioned reference data from reference-data/ into the ref and lib schemas.

Usage:  uv run python -m app.refdata.load [--only ref.countries,lib.units]

Every table and source file is listed in reference-data/manifest.json (load order matters
for foreign keys). Rows are upserted by their key, so re-running is safe. Writes go through
the normal audit triggers with source = 'refdata-loader'.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.db import close_pool, transaction

ROOT = Path(__file__).resolve().parents[3] / "reference-data"


def _rows_from(path: Path) -> list[dict]:
    if path.suffix == ".json":
        return json.loads(path.read_text())
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(line for line in fh if not line.startswith("#"))
        return [{k: (v if v != "" else None) for k, v in row.items()} for row in reader]


def load_table(tx, spec: dict) -> int:
    table: str = spec["table"]
    key: list[str] = spec["key"]
    json_cols = set(spec.get("json_columns", []))
    rows = _rows_from(ROOT / spec["file"])
    if not rows:
        return 0
    count = 0
    for row in rows:
        cols = list(row.keys())
        values = [json.dumps(row[c]) if c in json_cols and row[c] is not None else row[c] for c in cols]
        placeholders = ", ".join(f"%s::jsonb" if c in json_cols else "%s" for c in cols)
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in key)
        conflict = f"do update set {updates}" if updates else "do nothing"
        tx.execute(
            f"insert into {table} ({', '.join(cols)}) values ({placeholders}) "
            f"on conflict ({', '.join(key)}) {conflict}",
            values,
        )
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated table names to load")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    only = set(args.only.split(",")) if args.only else None
    with transaction(None) as tx:
        tx.execute("select set_config('app.source', 'refdata-loader', true)")
        for spec in manifest["tables"]:
            if only and spec["table"] not in only:
                continue
            n = load_table(tx, spec)
            print(f"  {spec['table']:<40} {n:>5} rows  <- {spec['file']}")
    close_pool()


if __name__ == "__main__":
    main()
