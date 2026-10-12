"""PDF sustainability report for an approved or locked project (PRD F14 C).

Sections: company and boundary, methodology, Scope 1/2/3, energy, water, waste, health & safety,
ESG KPIs, data-quality statement, factor sources, assumptions and limitations, assurance statement.
All text passes the wording guard: no claim of certification, audit or verification unless a
third-party verification is recorded.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports import wording_guard

GREEN = colors.HexColor("#1f5c45")
GRID = colors.HexColor("#d9dcd6")


def _fmt(v, digits: int = 2, unit: str = "") -> str:
    if v is None:
        return "Missing"
    if isinstance(v, (int, float, Decimal)):
        s = f"{float(v):,.{digits}f}"
        return f"{s} {unit}".strip()
    return str(v)


class _Doc:
    def __init__(self):
        base = getSampleStyleSheet()
        self.h1 = ParagraphStyle("h1", parent=base["Heading1"], textColor=GREEN, fontSize=18, spaceAfter=8)
        self.h2 = ParagraphStyle(
            "h2", parent=base["Heading2"], textColor=GREEN, fontSize=13, spaceBefore=10, spaceAfter=6
        )
        self.body = ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT)
        self.small = ParagraphStyle(
            "small", parent=self.body, fontSize=8, leading=10, textColor=colors.HexColor("#555555")
        )
        self.story: list = []
        self.texts: list[str] = []

    def p(self, text: str, style=None):
        self.texts.append(text)
        self.story.append(Paragraph(escape(text), style or self.body))

    def heading(self, text: str, level: int = 2):
        self.texts.append(text)
        self.story.append(Paragraph(escape(text), self.h1 if level == 1 else self.h2))

    def table(self, header: list[str], rows: list[list], widths: list[float] | None = None):
        cells = [[Paragraph(f"<b>{escape(h)}</b>", self.small) for h in header]]
        for r in rows:
            cells.append([Paragraph(escape(str(c)), self.small) for c in r])
            self.texts.extend(str(c) for c in r)
        t = Table(cells, colWidths=widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0ec")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        self.story.append(t)
        self.story.append(Spacer(1, 4 * mm))


def build_pdf(ds: dict) -> bytes:
    d = _Doc()
    c, p = ds["company"], ds["project"]
    verified = bool(ds["verifications"])
    m = {x["key"]: x for x in ds["metrics"]}

    d.heading(f"Sustainability report: {c['legal_name']}", 1)
    d.p(
        f"Reporting period {ds['period']['start']} to {ds['period']['end']} · Project {p['name']} ({p['stage']}) · "
        f"generated {datetime.now(UTC).strftime('%d %b %Y')}"
    )
    d.p(
        "This report is generated from the company's data on the platform. Every figure traces to the uploaded "
        "source data, the calculation applied and the emission factor used. Missing data is reported as Missing, "
        "never as zero.",
        d.small,
    )

    d.heading("1. Company and reporting boundary")
    d.table(
        ["Field", "Value"],
        [
            ["Legal name", c["legal_name"]],
            ["Country", c["country_code"]],
            ["Sector", c["sector_code"] or "—"],
            ["Reporting currency", c["reporting_currency"]],
            [
                "Boundary",
                "Whole organization" if p["boundary"] == "organization" else f"Division: {p['division_name']}",
            ],
        ],
        [60 * mm, 110 * mm],
    )
    d.table(
        ["Facility", "Type", "Location", "Status"],
        [
            [
                f["name"],
                f["facility_type"] or "company-level",
                f"{f['district'] or ''} {f['city'] or ''}".strip() or "—",
                f["operational_status"],
            ]
            for f in ds["facilities"]
        ],
        [60 * mm, 35 * mm, 45 * mm, 30 * mm],
    )

    d.heading("2. Methodology")
    d.p(
        "Emissions follow the GHG Protocol Corporate Standard structure (Scopes 1, 2 and 3). Every activity row is "
        "mapped by a person to an emission-factor category; the platform then resolves the factor valid for the "
        "row's period (country, then regional, then global), converts units using exact unit definitions or the "
        "factor's own published conversions, and multiplies quantity by factor in decimal arithmetic. The final "
        "kg CO2e is rounded once to six decimal places. Global warming potentials follow the factor source "
        "(IPCC AR5 for the seeded factor set). Scope 2 is location-based. No AI determines any reported number."
    )

    d.heading("3. Greenhouse gas emissions")
    d.table(
        ["Metric", "t CO2e", "Note"],
        [
            [m[k]["name"], _fmt(m[k]["value"], 3), m[k]["note"] or ""]
            for k in ("GHG_SCOPE_1", "GHG_SCOPE_2", "GHG_SCOPE_3", "GHG_TOTAL")
        ],
        [70 * mm, 30 * mm, 70 * mm],
    )
    d.table(
        ["Scope", "Category", "t CO2e", "Rows", "UNKNOWN rows"],
        [
            [x["scope"], f"{x['category_no'] or ''} {x['category']}", _fmt(x["co2e_t"], 3), x["rows"], x["unknown"]]
            for x in ds["categories"]
        ],
        [15 * mm, 75 * mm, 30 * mm, 20 * mm, 30 * mm],
    )

    d.heading("4. Energy")
    d.table(
        ["Metric", "Value", "Note"],
        [
            [m["ENERGY_TOTAL"]["name"], _fmt(m["ENERGY_TOTAL"]["value"], 0, "kWh"), m["ENERGY_TOTAL"]["note"] or ""],
            [m["ENERGY_RENEWABLE_SHARE"]["name"], _fmt(m["ENERGY_RENEWABLE_SHARE"]["value"], 1, "%"), ""],
            [
                m["ENERGY_INTENSITY"]["name"],
                _fmt(m["ENERGY_INTENSITY"]["value"], 2),
                m["ENERGY_INTENSITY"]["note"] or "",
            ],
        ],
        [60 * mm, 45 * mm, 65 * mm],
    )

    d.heading("5. Water")
    d.table(
        ["Metric", "Value", "Note"],
        [
            [m[k]["name"], _fmt(m[k]["value"], 0, "m3"), m[k]["note"] or ""]
            for k in ("WATER_WITHDRAWAL", "WATER_DISCHARGE", "WATER_CONSUMPTION")
        ],
        [60 * mm, 45 * mm, 65 * mm],
    )

    d.heading("6. Waste")
    d.table(
        ["Metric", "Value", "Note"],
        [
            [m["WASTE_TOTAL"]["name"], _fmt(m["WASTE_TOTAL"]["value"], 2, "t"), ""],
            [m["WASTE_HAZARDOUS"]["name"], _fmt(m["WASTE_HAZARDOUS"]["value"], 2, "t"), ""],
            [
                m["WASTE_RECYCLING_RATE"]["name"],
                _fmt(m["WASTE_RECYCLING_RATE"]["value"], 1, "%"),
                m["WASTE_RECYCLING_RATE"]["note"] or "",
            ],
        ],
        [60 * mm, 45 * mm, 65 * mm],
    )

    d.heading("7. Health and safety, and workforce")
    d.table(
        ["Metric", "Value", "Note"],
        [
            [m[k]["name"], _fmt(m[k]["value"], 2), m[k]["note"] or ""]
            for k in (
                "LTI_COUNT",
                "LTIFR",
                "INJURY_RATE",
                "FATALITIES",
                "LOST_DAYS",
                "HEADCOUNT_AVG",
                "TURNOVER_RATE",
                "TRAINING_HOURS_PER_EMPLOYEE",
            )
        ],
        [70 * mm, 35 * mm, 65 * mm],
    )

    d.heading("8. ESG KPIs and sources")
    d.table(
        ["KPI", "Value", "Unit", "Source module"],
        [[x["name"], _fmt(x["value"], 2), x["unit"] or "", x["source"]] for x in ds["metrics"]],
        [65 * mm, 30 * mm, 30 * mm, 45 * mm],
    )

    d.story.append(PageBreak())
    d.heading("9. Data quality statement")
    g = ds["grades"]
    d.p(
        "Each calculated value carries a quality grade: A primary measured data, B reliable secondary data, "
        "C estimated or default data (including all spend-based figures)."
    )
    d.table(
        ["Grade", "t CO2e", "Share"],
        [[k, _fmt(v["co2e_t"], 3), _fmt(v["share_pct"], 1, "%")] for k, v in g.items()],
        [30 * mm, 40 * mm, 40 * mm],
    )
    if ds["coverage_gaps"]:
        d.table(
            ["Category", "Facility", "Missing months"],
            [[x["terminal_name"], x["facility"], ", ".join(x["missing_months"])] for x in ds["coverage_gaps"]],
            [55 * mm, 45 * mm, 70 * mm],
        )

    d.heading("10. Emission factor sources")
    d.table(
        ["Database", "Year", "GWP", "Rows", "Advisor review"],
        [
            [s["source"], s["year"], s["gwp"], s["rows"], "pending" if s["pending_advisor_review"] else "complete"]
            for s in ds["factor_sources"]
        ],
        [85 * mm, 15 * mm, 25 * mm, 15 * mm, 30 * mm],
    )

    d.heading("11. Assumptions and limitations")
    if ds["assumptions"]:
        d.table(
            ["Category", "Assumption (Assumptions Register)"],
            [[a["category"], a["statement"]] for a in ds["assumptions"]],
            [35 * mm, 135 * mm],
        )
    else:
        d.p("No assumptions were recorded in the Assumptions Register for this project.")
    for t in ds["limitations"]:
        d.p(f"• {t}")

    d.heading("12. Assurance")
    if verified:
        for v in ds["verifications"]:
            d.p(
                f"Third-party assurance: {v['verifier']}, {v['standard']}, {v['assurance_level']} assurance, statement "
                f"dated {v['statement_date']}. Scope: {v['scope']}."
            )
    else:
        d.p(
            "No third-party assurance has been recorded for this report. It is prepared from company data and has "
            "not been independently reviewed."
        )

    wording_guard.check(d.texts, verified)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Sustainability report {c['legal_name']} {p['name']}",
    )
    doc.build(d.story)
    return buf.getvalue()
