"""LOCAL DEVELOPMENT ONLY: load demo customer data for "Sample Textiles Ltd" through the real API.

Usage: uv run python -m scripts.demo_data      (after `make bootstrap`)

Creates two clearly labelled demo projects - "FY 2025 (demo data)" (in review; its grid electricity
stays UNKNOWN because no cited Bangladesh grid factor covers 2025) and "FY 2026 (demo data)" (in
progress, January to September) - and fills every module via the same
endpoints the web app uses: template uploads, a bill-style manual entry, categorization, internal
review, labour, incidents and lab results. The numbers are invented demo activity data for a
fictional company; no emission factors, regulations or limits are created here.
"""

from __future__ import annotations

import calendar
import io
from datetime import date

import httpx
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.config import get_settings
from app.db import close_pool, transaction
from app.main import app
from scripts.bootstrap_dev import DEV_PASSWORD

COMPANY = "Sample Textiles Ltd"


def token(email: str) -> str:
    s = get_settings()
    r = httpx.post(
        f"{s.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": s.supabase_publishable_key},
        json={"email": email, "password": DEV_PASSWORD},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


class Api:
    def __init__(self, client: TestClient, email: str):
        self.c, self.h = client, {"Authorization": f"Bearer {token(email)}"}

    def get(self, path, **kw):
        r = self.c.get(path, headers=self.h, **kw)
        r.raise_for_status()
        return r

    def post(self, path, **kw):
        r = self.c.post(path, headers=self.h, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path}: {r.status_code} {r.text}")
        return r.json()

    def upload(self, pid, key, name, rows):
        tpl = self.get(f"/projects/{pid}/terminals/{key}/template").content
        wb = load_workbook(io.BytesIO(tpl))
        ws = wb["Data"]
        for r, values in enumerate(rows, start=2):
            for c, v in enumerate(values, start=1):
                ws.cell(row=r, column=c, value=v)
        buf = io.BytesIO()
        wb.save(buf)
        out = self.post(
            f"/projects/{pid}/terminals/{key}/uploads",
            files={"file": (name, buf.getvalue(), "application/octet-stream")},
        )
        assert out["validation_passed"], f"{name}: {out}"
        return out["file_id"]


def month_range(year: int, m: int) -> tuple[date, date]:
    return date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1])


def fill_project(api: Api, pid: str, year: int, last_month: int, scale: float) -> list[str]:
    """Upload one year (or part of it) of demo activity data; returns the file ids."""
    files = []
    ms = range(1, last_month + 1)
    seasonal = {m: 1 + 0.08 * ((m % 6) - 2.5) / 2.5 for m in range(1, 13)}

    def q(base: float, m: int) -> float:
        return round(base * scale * seasonal[m], 1)

    files.append(
        api.upload(
            pid,
            "s1_stationary",
            f"S1_Stationary_{year}.xlsx",
            [
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "Titas Gas",
                        "Boiler",
                        "Natural gas",
                        q(24500, m),
                        "m3",
                        "Metered / invoice",
                    ]
                    for m in ms
                ],
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "Padma Oil",
                        "Generator",
                        "Diesel",
                        q(3100, m),
                        "L",
                        "Metered / invoice",
                    ]
                    for m in ms
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s1_mobile",
            f"S1_Mobile_{year}.xlsx",
            [
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "Padma Oil",
                        "Pick-up truck",
                        "Diesel",
                        q(1150, m),
                        "L",
                        "Fuel receipts / fuel card",
                    ]
                    for m in ms
                ],
                *[
                    [
                        "Dhaka Head Office",
                        *month_range(year, m),
                        "Meghna Petroleum",
                        "Car",
                        "Petrol / Octane",
                        q(420, m),
                        "L",
                        "Fuel receipts / fuel card",
                    ]
                    for m in ms
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s1_fugitive",
            f"S1_Refrigerants_{year}.xlsx",
            [
                [
                    "Gazipur Factory",
                    date(year, 3, 1),
                    date(year, 3, 31),
                    "CoolServ BD",
                    "Chiller",
                    "R-410A",
                    12.5 * scale,
                    "kg",
                    "Service records",
                ],
                [
                    "Dhaka Head Office",
                    date(year, 5, 1),
                    date(year, 5, 31),
                    "CoolServ BD",
                    "Air-conditioning",
                    "HFC-32 (R-32)",
                    4 * scale,
                    "kg",
                    "Service records",
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s2_electricity",
            f"S2_Electricity_{year}.xlsx",
            [
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "BREB / Gazipur PBS",
                        "GZP-0001",
                        "Grid electricity",
                        q(126000, m),
                        "kWh",
                        q(1050000, m),
                        "Utility bill / meter reading",
                    ]
                    for m in ms
                ],
                *[
                    [
                        "Dhaka Head Office",
                        *month_range(year, m),
                        "DESCO",
                        "DSC-7781",
                        "Grid electricity",
                        q(9800, m),
                        "kWh",
                        q(98000, m),
                        "Utility bill / meter reading",
                    ]
                    for m in ms
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s3_c06",
            f"S3_Business_travel_{year}.xlsx",
            [
                [
                    "Company-level (all sites)",
                    date(year, 2, 1),
                    date(year, 2, 28),
                    "Travel desk",
                    "Flight, economy",
                    18400 * scale,
                    "pkm",
                    "Supplier or third-party data",
                ],
                [
                    "Company-level (all sites)",
                    date(year, 2, 1),
                    date(year, 2, 28),
                    "Travel desk",
                    "Hotel stay, India",
                    12,
                    "room_night",
                    "Supplier or third-party data",
                ],
                [
                    "Company-level (all sites)",
                    date(year, 6, 1),
                    date(year, 6, 30),
                    "Travel desk",
                    "Flight, business class",
                    9200 * scale,
                    "pkm",
                    "Supplier or third-party data",
                ],
                [
                    "Company-level (all sites)",
                    date(year, 6, 1),
                    date(year, 6, 30),
                    "Travel desk",
                    "Hotel stay, Bangladesh",
                    8,
                    "room_night",
                    "Supplier or third-party data",
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s3_c05",
            f"S3_Waste_{year}.xlsx",
            [
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "Green Recycling Ltd",
                        "Textiles & fabric offcuts",
                        "Recycling",
                        "No",
                        q(18, m),
                        "t",
                        "Weighbridge / manifest",
                    ]
                    for m in ms
                ],
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "City Corporation",
                        "Commercial & industrial waste (mixed)",
                        "Landfill",
                        "No",
                        q(6.5, m),
                        "t",
                        "Weighbridge / manifest",
                    ]
                    for m in ms
                ],
                *[
                    [
                        "Gazipur Factory",
                        *month_range(year, m),
                        "Licensed hazardous handler",
                        "Sludge (ETP)",
                        "Treatment",
                        "Yes",
                        q(2.2, m),
                        "t",
                        "Weighbridge / manifest",
                    ]
                    for m in ms
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "s3_spend",
            f"S3_Spend_{year}.xlsx",
            [
                [
                    "Company-level (all sites)",
                    date(year, 1, 1),
                    date(year, 6, 30),
                    "Dye suppliers",
                    "Synthetic dyes & pigments",
                    38_500_000 * scale,
                    "BDT",
                    "Accounting records / invoices",
                ],
                [
                    "Company-level (all sites)",
                    date(year, 1, 1),
                    date(year, 6, 30),
                    "Carton suppliers",
                    "Corrugated & solid fibre boxes",
                    12_200_000 * scale,
                    "BDT",
                    "Accounting records / invoices",
                ],
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "water_withdrawal",
            f"Water_withdrawal_{year}.xlsx",
            [
                [
                    "Gazipur Factory",
                    *month_range(year, m),
                    "Groundwater",
                    "DTW-1",
                    q(41000, m),
                    "m3",
                    "Metered / invoice",
                ]
                for m in ms
                if not (year == 2026 and m == 4)  # April 2026 meter reading missing: shown as Missing
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "water_discharge",
            f"Water_discharge_{year}.xlsx",
            [
                [
                    "Gazipur Factory",
                    *month_range(year, m),
                    "Surface water (river/canal)",
                    "Treated in own ETP",
                    q(34500, m),
                    "m3",
                    "Metered / invoice",
                ]
                for m in ms
            ],
        )
    )
    files.append(
        api.upload(
            pid,
            "energy_renewable",
            f"Solar_{year}.xlsx",
            [
                ["Gazipur Factory", *month_range(year, m), "Solar PV", q(7200, m), "kWh", "Metered / invoice"]
                for m in ms
            ],
        )
    )
    return files


def main() -> None:
    with TestClient(app) as client:
        sm = Api(client, "s.akter@sample.test")
        reviewer = Api(client, "reviewer@platform.test")
        with transaction(None) as tx:
            company_id = str(tx.scalar("select id from public.companies where legal_name = %s", (COMPANY,)))
            existing = tx.scalar(
                "select count(*) from public.projects where company_id = %s and name like %s",
                (company_id, "% (demo data)"),
            )
            facilities = {
                r["name"]: str(r["id"])
                for r in tx.all("select id, name from public.facilities where company_id = %s", (company_id,))
            }
        if existing:
            print("Demo projects already exist; nothing to do.")
            return

        for year, last_month, scale, stages in (
            (2025, 12, 1.0, ("DATA_COLLECTION", "REVIEW")),
            (2026, 9, 1.04, ("DATA_COLLECTION",)),
        ):
            pid = sm.post(
                "/projects",
                json={
                    "company_id": company_id,
                    "name": f"FY {year} (demo data)",
                    "period_type": "year",
                    "start_date": f"{year}-01-01",
                    "end_date": f"{year}-12-31",
                    "upload_deadline": f"{year + 1}-03-31",
                },
            )["id"]
            files = fill_project(sm, pid, year, last_month, scale)
            for key in ("s1_stationary", "s1_mobile", "s1_fugitive", "s2_electricity", "s3_c06", "s3_c05", "s3_spend"):
                sm.post(f"/projects/{pid}/terminals/{key}/categorizations/accept-suggested")
            with transaction(None) as tx:
                rows = tx.all(
                    "select file_id, terminal_key, status from public.v_file_status where project_id = %s", (pid,)
                )
            for r in rows:
                if r["status"] == "AWAITING_CONFIRMATION":
                    sm.post(f"/files/{r['file_id']}/confirm-rows")
                elif r["status"] == "PRELIMINARY":
                    reviewer.post(f"/files/{r['file_id']}/review", json={"action": "confirm"})
            for key, reason in (
                ("s2_heating", "No purchased heat"),
                ("s2_steam", "No purchased steam"),
                ("s2_cooling", "No purchased cooling"),
                ("s3_c04", "Template pending the domain advisor"),
            ):
                sm.c.patch(
                    f"/projects/{pid}/categories/{key}", headers=sm.h, json={"in_scope": False, "na_reason": reason}
                )
            for to in stages:
                sm.post(f"/projects/{pid}/transition", json={"to": to})
            for kind, value, unit in (
                ("production_mass", 2400 * scale * last_month / 12, "t"),
                ("employees", 1850, "employees"),
                ("revenue", 3_200_000_000 * scale * last_month / 12, "BDT"),
            ):
                with transaction(None) as tx:
                    tx.execute(
                        "insert into public.denominators (company_id, project_id, kind, value, unit) "
                        "values (%s, %s, %s, %s, %s)",
                        (company_id, pid, kind, value, unit),
                    )
            print(f"FY {year}: {len(files)} files loaded")

        # Labour and incidents (company data by month, not tied to one project)
        with transaction(None) as tx:
            tx.execute("select set_config('app.source', 'demo-data', true)")
            for year, last in ((2025, 12), (2026, 9)):
                for m in range(1, last + 1):
                    for fac, perm, temp, female in (
                        ("Gazipur Factory", 1620, 110, 1050),
                        ("Dhaka Head Office", 112, 8, 41),
                    ):
                        total = perm + temp
                        tx.execute(
                            """insert into public.labour_monthly (company_id, facility_id, month, headcount_permanent,
                                 headcount_temporary, headcount_female, headcount_male, new_hires, departures,
                                 working_hours, overtime_hours, training_hours)
                               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing""",
                            (
                                company_id,
                                facilities[fac],
                                date(year, m, 1),
                                perm,
                                temp,
                                female,
                                total - female,
                                (m % 4) + 2 if fac.startswith("Gaz") else 1,
                                (m % 3) + 2 if fac.startswith("Gaz") else 1,
                                total * 208,
                                total * 18,
                                total * 1.5,
                            ),
                        )
            for occurred, typ, sev, lost, days in (
                (date(2025, 2, 11), "injury", "moderate", True, 5),
                (date(2025, 7, 3), "near_miss", "minor", False, 0),
                (date(2025, 10, 21), "injury", "minor", False, 0),
                (date(2026, 3, 8), "fire", "moderate", False, 0),
                (date(2026, 6, 17), "injury", "major", True, 12),
            ):
                tx.execute(
                    """insert into public.incidents (company_id, facility_id, occurred_on, type, severity,
                         workers_affected, lost_time, lost_days, root_cause)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, 'Demo data')""",
                    (
                        company_id,
                        facilities["Gazipur Factory"],
                        occurred,
                        typ,
                        sev,
                        1 if typ == "injury" else 0,
                        lost,
                        days,
                    ),
                )
            for d in (date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15)):
                for param, value in (("ph", 7.4), ("bod5", 24), ("cod", 162), ("tss", 61)):
                    tx.execute(
                        "insert into public.wq_samples (company_id, facility_id, sample_date, parameter_key, value, "
                        "lab_name) values (%s, %s, %s, %s, %s, 'Demo lab')",
                        (company_id, facilities["Gazipur Factory"], d, param, value),
                    )
    close_pool()
    print("Demo data loaded for", COMPANY)


if __name__ == "__main__":
    main()
