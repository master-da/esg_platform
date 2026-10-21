"""Write the demo activity data as upload-ready CSV files (no database, no users).

Usage: uv run python -m scripts.export_demo_files [out_dir]      (default: ../demo/upload)

Uses the same rows as scripts.demo_data, so the files can be uploaded through the website on a
deployment where the dev users must not exist. Each file carries its category template's headers,
so the upload page recognises it by header signature. Facility names must match the company's
facilities exactly: "Gazipur Factory", "Dhaka Head Office" and the automatic "Company-level (all sites)".
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

from scripts.demo_data import fill_project

TERMINALS = Path(__file__).resolve().parents[2] / "reference-data" / "terminals"


class CsvWriter:
    """Stands in for the API client in fill_project: writes each 'upload' to a CSV file."""

    def __init__(self, out: Path):
        self.out = out

    def upload(self, pid: str, key: str, name: str, rows: list[list]) -> str:
        headers = [c["header"] for c in json.loads((TERMINALS / f"{key}.json").read_text())["config"]["columns"]]
        path = self.out / pid / name.replace(".xlsx", ".csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in rows:
                w.writerow([v.isoformat() if isinstance(v, date) else v for v in r])
        return str(path)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "demo" / "upload"
    writer = CsvWriter(out)
    for folder, year, last_month, scale in (("FY2025", 2025, 12, 1.0), ("FY2026", 2026, 9, 1.04)):
        for p in fill_project(writer, folder, year, last_month, scale):
            print(Path(p).relative_to(out))


if __name__ == "__main__":
    main()
