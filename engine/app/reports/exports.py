"""Excel / CSV exports (PRD F14 C) and the audit export.

One generic exporter serves every framework layout: rows come from ref.framework_metric_mappings,
values from the shared report dataset. Adding a framework is mapping rows only.
Missing values are written as "Missing", never as 0. The audit export contains no factor codes.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.db import Tx

HEADER_FILL = PatternFill("solid", fgColor="E8F0EC")
SECTIONS = {
    "emissions_by_ghg_category": "Emissions by GHG category",
    "emissions_by_internal_category": "Emissions by internal category",
    "energy_water_waste": "Energy, water & waste",
    "calculation_trail": "Calculation trail",
    "assumptions_quality": "Assumptions & data quality",
}

AUDIT_COLUMNS = [
    "Source file",
    "Source row",
    "Supplier",
    "Facility",
    "Period start",
    "Period end",
    "Input value",
    "Input unit",
    "Category (description path)",
    "Conversion factor",
    "Conversion from",
    "Conversion to",
    "Emission factor (kg CO2e per unit)",
    "Emission factor unit (per)",
    "Emission factor database",
    "Database year",
    "Library version",
    "GWP",
    "Calculated GHG (kg CO2e)",
    "Calculated GHG (t CO2e)",
    "Data quality grade",
    "Calculation version",
    "Status",
    "Formula",
]


def _val(v):
    if v is None:
        return "Missing"
    if isinstance(v, Decimal):
        return float(v) if v == v.to_integral_value() or abs(v) < Decimal("1e15") else str(v)
    return v


def _exact(v):
    """Full-precision text for audit recomputation (no float rounding)."""
    return "" if v is None else format(v, "f") if isinstance(v, Decimal) else v


def _sheet(wb: Workbook, title: str, header: list[str], rows: list[list]) -> None:
    ws = wb.create_sheet(title[:31])
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = HEADER_FILL
    for r in rows:
        ws.append(r)
    for i, h in enumerate(header, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(48, len(h) + 4))
    ws.freeze_panes = "A2"


def _summary(ds: dict, title: str) -> list[list]:
    p, c = ds["project"], ds["company"]
    ver = ds["verifications"]
    return [
        ["Report", title],
        ["Company", c["legal_name"]],
        ["Project", p["name"]],
        ["Project stage", p["stage"]],
        ["Period", f"{ds['period']['start']} to {ds['period']['end']}"],
        ["Generated", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")],
        [
            "Third-party assurance",
            "; ".join(f"{v['verifier']} ({v['standard']}, {v['assurance_level']}, {v['statement_date']})" for v in ver)
            if ver
            else "None recorded",
        ],
        [
            "Note",
            "Missing values are shown as Missing, never as 0. Rows without an emission factor are excluded "
            "and listed as UNKNOWN.",
        ],
    ]


def framework_rows(tx: Tx, ds: dict, framework: str) -> list[list]:
    mappings = tx.all(
        """select m.disclosure_ref, m.disclosure_title, m.metric_key from ref.framework_metric_mappings m
                         where m.framework_key = %s order by m.sort""",
        (framework,),
    )
    by_key = {m["key"]: m for m in ds["metrics"]}
    rows = []
    for mp in mappings:
        m = by_key.get(mp["metric_key"])
        if not m:
            continue
        rows.append(
            [
                mp["disclosure_ref"],
                mp["disclosure_title"] or "",
                m["name"],
                _val(m["value"]),
                m["unit"] or "",
                m["status"],
                m["note"] or "",
                m["source"],
            ]
        )
    return rows


DISCLOSURE_HEADER = ["Disclosure", "Title", "Metric", "Value", "Unit", "Status", "Note", "Source module"]


def section_rows(ds: dict, section: str) -> tuple[list[str], list[list]]:
    if section == "emissions_by_ghg_category":
        return (
            ["Scope", "No.", "Category", "t CO2e", "Rows", "Rows without factor (UNKNOWN)"],
            [
                [c["scope"], c["category_no"], c["category"], _val(c["co2e_t"]), c["rows"], c["unknown"]]
                for c in ds["categories"]
            ],
        )
    if section == "emissions_by_internal_category":
        return (
            ["Category (description path)", "t CO2e", "Calculated rows"],
            [[r["label"], _val(r["co2e_t"]), r["records"]] for r in ds["by_path"]],
        )
    if section == "energy_water_waste":
        keys = (
            "ENERGY_TOTAL",
            "ENERGY_RENEWABLE_SHARE",
            "ENERGY_INTENSITY",
            "WATER_WITHDRAWAL",
            "WATER_DISCHARGE",
            "WATER_CONSUMPTION",
            "WASTE_TOTAL",
            "WASTE_HAZARDOUS",
            "WASTE_RECYCLED",
            "WASTE_RECYCLING_RATE",
        )
        return (
            ["Metric", "Value", "Unit", "Status", "Note", "Source module"],
            [
                [m["name"], _val(m["value"]), m["unit"] or "", m["status"], m["note"] or "", m["source"]]
                for m in ds["metrics"]
                if m["key"] in keys
            ],
        )
    if section == "calculation_trail":
        return AUDIT_COLUMNS, [audit_row(r) for r in ds["rows"]]
    if section == "assumptions_quality":
        rows = [["Assumption", a["category"], a["statement"]] for a in ds["assumptions"]]
        rows += [["Limitation", "system", t] for t in ds["limitations"]]
        rows += [
            [
                "Data quality",
                f"Grade {g}",
                f"{_val(v['co2e_t'])} t CO2e" + (f" ({v['share_pct']:.1f}%)" if v["share_pct"] is not None else ""),
            ]
            for g, v in ds["grades"].items()
        ]
        return ["Type", "Category", "Statement"], rows
    raise ValueError(section)


def audit_row(r: dict) -> list:
    return [
        r.get("file_name") or "manual entry",
        r.get("source_row"),
        r.get("supplier_name"),
        r.get("facility"),
        r["period_start"],
        r["period_end"],
        _exact(r["input_quantity"]),
        r["input_unit"],
        r["taxonomy_display"],
        _exact(r["conversion_multiplier"]),
        r["conversion_from"] or "",
        r["conversion_to"] or "",
        _exact(r["factor_value"]),
        r["factor_unit"] or "",
        r["factor_source_name"] or "",
        r["factor_source_year"],
        r["factor_version"],
        r["gwp_version"] or "",
        _exact(r["co2e_kg"]),
        _exact(r["co2e_t"]),
        r["quality_grade"],
        r.get("version_no"),
        r["status"],
        r["formula"] or r["message"] or "",
    ]


def to_csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows([[_val(c) if not isinstance(c, str) else c for c in r] for r in rows])
    return buf.getvalue().encode("utf-8-sig")


def build_xlsx(tx: Tx, ds: dict, export_type: str, sections: list[str]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    title = {"custom": "Custom export", "audit": "Audit export"}.get(export_type, f"{export_type} layout")
    _sheet(wb, "Summary", ["Field", "Value"], _summary(ds, title))
    if export_type == "audit":
        _sheet(wb, "Calculations", AUDIT_COLUMNS, [audit_row(r) for r in ds["rows"]])
        _sheet(
            wb,
            "Version history",
            ["Version", "Reason", "Library as of", "Created", "Created by", "Frozen"],
            [
                [
                    v["version_no"],
                    v["reason"],
                    v["library_as_of"].replace(tzinfo=None),
                    v["created_at"].replace(tzinfo=None),
                    v["created_by"],
                    v["frozen_at"].replace(tzinfo=None) if v["frozen_at"] else "",
                ]
                for v in ds["versions"]
            ],
        )
        _sheet(
            wb,
            "Factor sources",
            ["Database", "Year", "GWP", "Calculated rows", "Pending advisor review", "URL"],
            [
                [s["source"], s["year"], s["gwp"], s["rows"], "yes" if s["pending_advisor_review"] else "no", s["url"]]
                for s in ds["factor_sources"]
            ],
        )
        h, rows = section_rows(ds, "assumptions_quality")
        _sheet(wb, "Assumptions & quality", h, rows)
    elif export_type == "custom":
        for s in sections:
            h, rows = section_rows(ds, s)
            _sheet(wb, SECTIONS[s], h, rows)
    else:
        _sheet(wb, "Disclosures", DISCLOSURE_HEADER, framework_rows(tx, ds, export_type))
        for s in sections:
            h, rows = section_rows(ds, s)
            _sheet(wb, SECTIONS[s], h, rows)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_csv(tx: Tx, ds: dict, export_type: str, sections: list[str]) -> bytes:
    if export_type == "audit":
        return to_csv(AUDIT_COLUMNS, [audit_row(r) for r in ds["rows"]])
    if export_type == "custom":
        h, rows = section_rows(ds, sections[0] if sections else "emissions_by_ghg_category")
        return to_csv(h, rows)
    return to_csv(DISCLOSURE_HEADER, framework_rows(tx, ds, export_type))
