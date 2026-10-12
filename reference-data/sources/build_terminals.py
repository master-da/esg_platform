"""Generate reference-data/terminals/*.json (one upload terminal per scope/category, PRD F5) and
reference-data/lib/categorization_rules.json (deterministic suggestions, PRD F6).

Column layouts, units and rules are PROVISIONAL (template_version 0.x) pending the domain advisor's
sign-off; changing them is a data change only. Run: python reference-data/sources/build_terminals.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1-provisional"

STD_BASIS = {"Metered / invoice": "A", "Supplier or third-party data": "B", "Estimate": "C"}
SPEND_BASIS = {"Accounting records / invoices": "C", "Estimate": "C"}   # spend-based is always grade C (PRD 5.1)


def facility():
    return {"key": "facility", "header": "Facility", "type": "facility", "required": True}


def period(start="Period start", end="Period end"):
    return [{"key": "period_start", "header": start, "type": "date", "required": True},
            {"key": "period_end", "header": end, "type": "date", "required": True}]


def supplier(header="Supplier", required=False):
    return {"key": "supplier_name", "header": header, "type": "text", "required": required}


def enum(key, header, options, required=True):
    return {"key": key, "header": header, "type": "enum", "required": required, "options": options}


def qty(header="Quantity"):
    return {"key": "quantity", "header": header, "type": "decimal", "required": True, "min": 0, "role": "quantity"}


def unit(options):
    return {"key": "unit", "header": "Unit", "type": "unit", "required": True, "role": "unit", "options": options}


def basis(grades):
    return {"key": "data_basis", "header": "Data basis", "type": "enum", "required": True, "role": "data_basis",
            "options": list(grades)}


NOTES = {"key": "notes", "header": "Notes", "type": "text", "required": False}
PERIOD_RULES = [{"type": "period_order"}, {"type": "period_within_project"}]


def terminal(key, scope, cat_no, name, description, excludes, instructions, root, columns, cat_keys, grades,
             rules, activity_type, sort, *, canonical=None, enabled=True, disabled_reason=None, accepts_bills=False,
             extra=None, default_grade=None, module="ghg"):
    cfg = {"activity_type": activity_type, "columns": columns, "categorization_keys": cat_keys,
           "quality_grades": grades, "canonical_units": canonical or {"volume": "L", "mass": "kg", "energy": "kWh"},
           "rules": [*rules, *PERIOD_RULES]}
    if default_grade:
        cfg["default_grade"] = default_grade
    cfg.update(extra or {})
    return {"key": key, "module": module, "scope": scope, "category_no": cat_no, "name": name,
            "description": description, "excludes": excludes, "instructions": instructions, "taxonomy_root": root,
            "accepts_bills": accepts_bills, "enabled": enabled, "disabled_reason": disabled_reason,
            "template_version": VERSION, "sort": sort, "config": cfg}


FUEL_DIMS = {"type": "unit_dimension_in", "dimensions": ["volume", "mass", "energy"],
             "problem": "Distance or other non-fuel quantity entered for a fuel category",
             "fix": "Enter the fuel quantity (volume, mass or energy). Distance-based travel belongs in Scope 3."}
ENERGY_ONLY = {"type": "unit_dimension_in", "dimensions": ["energy"],
               "problem": "This category expects an energy quantity", "fix": "Enter kWh, MWh, GJ or MMBtu."}
CURRENCY_ONLY = {"type": "unit_dimension_in", "dimensions": ["currency"],
                 "problem": "Spend-based categories expect an amount of money", "fix": "Enter the amount in BDT or USD."}
MASS_ONLY = {"type": "unit_dimension_in", "dimensions": ["mass"],
             "problem": "Volume figure entered under a kg-only column", "fix": "Change the unit or the column"}

TERMINALS = []
RULES = []


def rules_for(terminal_key, column, mapping):
    for value, code in mapping.items():
        RULES.append({"terminal_key": terminal_key, "match": {column: value.casefold()}, "taxonomy_code": code,
                      "priority": 100, "note": None})


# --- Scope 1 -----------------------------------------------------------------------------
STATIONARY_FUELS = {"Natural gas": "01010000001101", "LPG": "01010000001102", "CNG": "01010000001103",
                    "Petrol / Octane": "01010000001201", "Diesel": "01010000001202",
                    "Furnace oil": "01010000001203", "Kerosene": "01010000001204", "Gas oil": "01010000001205",
                    "Coal": "01010000001301"}
TERMINALS.append(terminal(
    "s1_stationary", 1, "1.2", "Stationary combustion",
    "Fuel burned on site in fixed equipment: boilers, generators, furnaces, ovens, dryers and stenters.",
    "Fuel for vehicles goes in Mobile combustion. Purchased electricity, heat or steam go in Scope 2. "
    "Distance inputs are rejected here.",
    "One row per facility, fuel and period, from fuel invoices, gas bills (e.g. Titas Gas) or generator logs.",
    "s1.stationary",
    [facility(), *period(), supplier("Fuel supplier"),
     enum("equipment_type", "Equipment", ["Boiler", "Generator", "Furnace / oven", "Dryer / stenter", "Other equipment"]),
     enum("fuel_type", "Fuel type", list(STATIONARY_FUELS)), qty("Fuel quantity"),
     unit(["m3", "L", "kg", "t", "kWh", "MMBtu", "gal_us"]), basis(STD_BASIS), NOTES],
    ["fuel_type"], STD_BASIS, [FUEL_DIMS], "fuel_combustion_stationary", 12))
rules_for("s1_stationary", "fuel_type", STATIONARY_FUELS)

MOBILE_FUELS = {"Diesel": "01020000010001", "Petrol / Octane": "01020000010002", "CNG": "01020000010003",
                "LPG": "01020000010004"}
TERMINALS.append(terminal(
    "s1_mobile", 1, "1.3", "Mobile combustion",
    "Fuel used by vehicles the company owns or controls (cars, pick-ups, vans, trucks, buses, motorbikes, forklifts).",
    "Upload fuel quantities only. Electricity used by electric vehicles goes in Scope 2; distance travelled in "
    "vehicles you do not control goes in Scope 3 (business travel or commuting).",
    "One row per vehicle (or vehicle group), fuel and period. Enter the fuel quantity from fuel receipts, fuel cards "
    "or logbooks. Choose the data basis that matches the evidence you hold.",
    "s1.mobile",
    [facility(), *period(), supplier("Fuel supplier"),
     enum("vehicle_type", "Vehicle type", ["Car", "Pick-up truck", "Delivery van", "Truck", "Bus", "Motorbike",
                                           "Forklift", "Other vehicle"]),
     enum("fuel_type", "Fuel type", list(MOBILE_FUELS)), qty("Fuel quantity"),
     unit(["L", "m3", "gal_us", "kg", "t", "kWh"]),
     basis({"Fuel receipts / fuel card": "A", "Supplier statement": "B", "Estimate": "C"}), NOTES],
    ["vehicle_type", "fuel_type"], {"Fuel receipts / fuel card": "A", "Supplier statement": "B", "Estimate": "C"},
    [FUEL_DIMS], "fuel_combustion_mobile", 13))
rules_for("s1_mobile", "fuel_type", MOBILE_FUELS)

GASES = {"HFC-134a": "01030000010001", "HFC-32 (R-32)": "01030000010002", "R-410A": "01030000010003",
         "R-404A": "01030000010004", "R-407C": "01030000010005"}
TERMINALS.append(terminal(
    "s1_fugitive", 1, "1.1", "Fugitive emissions (refrigerants)",
    "Refrigerant and other greenhouse gases leaked from equipment you control: air-conditioning, chillers, "
    "refrigeration and fire suppression.",
    "Enter the mass of gas lost (top-ups or recharges), not the equipment's total charge. HCFC-22 (R-22) is a "
    "Montreal Protocol gas and is not reported in Scope 1.",
    "Use service records: kilograms of refrigerant added during the period, by gas.",
    "s1.fugitive",
    [facility(), *period(), supplier("Service company"),
     enum("equipment_type", "Equipment", ["Air-conditioning", "Chiller", "Refrigeration", "Fire suppression", "Other"]),
     enum("gas", "Refrigerant / gas", [*GASES, "Other gas"]), qty("Gas lost (topped up)"), unit(["kg", "t"]),
     basis({"Service records": "A", "Supplier estimate": "B", "Estimate": "C"}), NOTES],
    ["gas"], {"Service records": "A", "Supplier estimate": "B", "Estimate": "C"}, [MASS_ONLY], "fugitive_refrigerant", 11,
    canonical={"mass": "kg"}))
rules_for("s1_fugitive", "gas", GASES)

# --- Scope 2 -----------------------------------------------------------------------------
TERMINALS.append(terminal(
    "s2_electricity", 2, "2.1", "Purchased electricity",
    "Electricity bought from the national grid or a utility (DESCO, DPDC, BREB/PBS, NESCO, WZPDCL …) and consumed "
    "at your facilities.",
    "Electricity generated on site from your own diesel or gas generators is Scope 1 stationary combustion (enter "
    "the fuel). On-site solar generation is entered in the Energy module.",
    "One row per meter (or facility) and billing period, with the kWh consumed from the bill. You can also upload a "
    "bill PDF or photo: the system proposes the values and you confirm them.",
    "s2.electricity",
    [facility(), *period("Billing period start", "Billing period end"), supplier("Utility / supplier", True),
     {"key": "meter_id", "header": "Meter / account no.", "type": "text", "required": False},
     enum("electricity_type", "Electricity type", ["Grid electricity"]), qty("Electricity consumed"),
     unit(["kWh", "MWh"]),
     {"key": "amount_billed", "header": "Amount billed (BDT)", "type": "decimal", "required": False, "min": 0},
     basis({"Utility bill / meter reading": "A", "Landlord or supplier statement": "B", "Estimate": "C"}), NOTES],
    ["electricity_type"], {"Utility bill / meter reading": "A", "Landlord or supplier statement": "B", "Estimate": "C"},
    [{**ENERGY_ONLY, "problem": "Purchased electricity expects an energy quantity",
      "fix": "Enter consumption in kWh or MWh from the bill."}], "electricity_purchased", 21,
    canonical={"energy": "kWh"}, accepts_bills=True,
    extra={"bill_fields": {"period_start": "Billing period start", "period_end": "Billing period end",
                           "quantity": "kWh consumed", "amount_billed": "Amount billed (BDT)",
                           "meter_id": "Meter / account no.", "supplier_name": "Utility"}}))
rules_for("s2_electricity", "electricity_type", {"Grid electricity": "02010000010001"})

for key, no, name, root, label, code, sort in [
    ("s2_heating", "2.2", "Purchased heating", "s2.heating", "Purchased heat", "02020000010001", 22),
    ("s2_steam", "2.3", "Purchased steam", "s2.steam", "Purchased steam", "02030000010001", 23),
    ("s2_cooling", "2.4", "Purchased cooling", "s2.cooling", "Purchased cooling / chilled water", "02040000010001", 24),
]:
    TERMINALS.append(terminal(
        key, 2, no, name, f"{label} bought from a third party (e.g. a neighbouring plant or a district system).",
        "Heat or steam you produce yourself from fuel is Scope 1 stationary combustion (enter the fuel).",
        "One row per supplier and period with the energy delivered, from the supplier's invoice.",
        root,
        [facility(), *period(), supplier("Supplier", True), enum("energy_type", "Energy type", [label]),
         qty("Energy delivered"), unit(["kWh", "MWh", "GJ", "MMBtu"]), basis(STD_BASIS), NOTES],
        ["energy_type"], STD_BASIS, [ENERGY_ONLY], key.replace("s2_", "purchased_"), sort, canonical={"energy": "kWh"}))
    rules_for(key, "energy_type", {label: code})

# --- Scope 3 -----------------------------------------------------------------------------
SPEND = {"Broadwoven fabric": "03990000010001", "Knit fabric": "03990000010002",
         "Textile & fabric finishing services": "03990000010003", "Cut-and-sew apparel": "03990000010004",
         "Synthetic dyes & pigments": "03990000020001", "Basic organic chemicals": "03990000020002",
         "Other chemical products": "03990000020003", "Corrugated & solid fibre boxes": "03990000030001",
         "Plastic bags & pouches": "03990000030002", "Other plastic products": "03990000030003",
         "Engineering services": "03990000040001", "Management consulting": "03990000040002",
         "Temporary staffing": "03990000040003", "Cleaning & janitorial": "03990000040004",
         "Property & casualty insurance": "03990000040005", "Freight trucking": "03990000050001",
         "Freight forwarding & arrangement": "03990000050002"}
SPEND_UNITS = ["BDT", "USD"]
TERMINALS.append(terminal(
    "s3_spend", 3, "3.0", "Spend-based (all Scope 3 purchases)",
    "Money spent on purchased goods and services when quantities are not available. Spend-based estimates are "
    "always graded C (estimated).",
    "Prefer activity data where you have it (e.g. tonnes of material in Purchased goods and services). Do not "
    "enter the same purchases in both places.",
    "One row per spend category, supplier and period, from the accounting ledger. BDT amounts are converted to USD "
    "with the cited annual exchange rate.",
    "s3.spend",
    [facility(), *period(), supplier("Supplier"), enum("spend_category", "Spend category", [*SPEND, "Other"]),
     qty("Amount spent"), unit(SPEND_UNITS), basis(SPEND_BASIS), NOTES],
    ["spend_category"], SPEND_BASIS, [CURRENCY_ONLY], "spend", 30, default_grade="C",
    canonical={"currency": "BDT"}))
rules_for("s3_spend", "spend_category", SPEND)

MATERIALS = {"Clothing / finished textiles": "03010000010001", "Plastics": "03010000010002",
             "Paper & board": "03010000010003", "Metal cans": "03010000010004"}
TERMINALS.append(terminal(
    "s3_c01", 3, "3.1", "Purchased goods and services",
    "Materials and products you buy, entered by mass (tonnes or kg) where known.",
    "Purchases known only as money spent go in Spend-based. Fuel and electricity go in Scope 1, 2 and category 3.3.",
    "One row per material, supplier and period, from purchase records or goods-received notes.",
    "s3.c01",
    [facility(), *period(), supplier("Supplier"), enum("material", "Material", [*MATERIALS, "Other material"]),
     qty("Quantity purchased"), unit(["kg", "t"]), basis(STD_BASIS), NOTES],
    ["material"], STD_BASIS, [{**MASS_ONLY, "problem": "Materials are entered by mass", "fix": "Enter kg or tonnes."}],
    "purchased_goods_mass", 31, canonical={"mass": "kg"}))
rules_for("s3_c01", "material", MATERIALS)

CAPITAL = {"Industrial machinery": "03020000010001", "Computers & IT hardware": "03020000010002",
           "Building construction": "03020000010003"}
TERMINALS.append(terminal(
    "s3_c02", 3, "3.2", "Capital goods",
    "Machinery, equipment, IT hardware and buildings bought during the period (spend-based, grade C).",
    "Do not include them again in Spend-based or Purchased goods and services.",
    "One row per asset type and supplier, with the amount paid in the period.",
    "s3.c02",
    [facility(), *period(), supplier("Supplier"), enum("asset_type", "Asset type", [*CAPITAL, "Other asset"]),
     qty("Amount spent"), unit(SPEND_UNITS), basis(SPEND_BASIS), NOTES],
    ["asset_type"], SPEND_BASIS, [CURRENCY_ONLY], "capital_goods_spend", 32, default_grade="C",
    canonical={"currency": "BDT"}))
rules_for("s3_c02", "asset_type", CAPITAL)

WTT = {"Natural gas": "03030000010001", "Diesel": "03030000010002", "Petrol / Octane": "03030000010003",
       "Furnace oil": "03030000010004", "LPG": "03030000010005", "CNG": "03030000010006"}
TERMINALS.append(terminal(
    "s3_c03", 3, "3.3", "Fuel- and energy-related activities",
    "Upstream (well-to-tank) emissions of the fuels you burned: extraction, refining and transport of the fuel.",
    "Enter the same fuel quantities reported in Scope 1. Transmission and distribution losses of electricity are "
    "not yet covered (no cited Bangladesh factor).",
    "One row per fuel and period, copying the Scope 1 quantities.",
    "s3.c03",
    [facility(), *period(), supplier("Fuel supplier"), enum("fuel_type", "Fuel type", list(WTT)), qty("Fuel quantity"),
     unit(["L", "m3", "kg", "t"]), basis(STD_BASIS), NOTES],
    ["fuel_type"], STD_BASIS, [FUEL_DIMS], "fuel_wtt", 33))
rules_for("s3_c03", "fuel_type", WTT)

FREIGHT = {"Truck (HGV)": "-", "Van (diesel)": "-", "Container ship": "-"}
TERMINALS.append(terminal(
    "s3_c04", 3, "3.4", "Upstream transportation and distribution",
    "Transport of purchased goods to you, paid for by you, in vehicles you do not own.",
    None, None, "s3.c04",
    [facility(), *period(), supplier("Transport provider"), enum("transport_mode", "Transport mode", list(FREIGHT)),
     qty("Tonne-km"), unit(["tkm"]), basis(STD_BASIS), NOTES],
    ["transport_mode"], STD_BASIS, [], "upstream_transport", 34, enabled=False,
    disabled_reason="The template for this category is pending the domain advisor's design (PRD Feature 5)."))

WASTE = {("Commercial & industrial waste (mixed)", "Landfill"): "03050000010001",
         ("Commercial & industrial waste (mixed)", "Incineration with energy recovery"): "03050000010002",
         ("Plastics", "Landfill"): "03050000020001", ("Plastics", "Recycling"): "03050000020002",
         ("Plastics", "Incineration with energy recovery"): "03050000020003",
         ("Paper & board", "Recycling"): "03050000030001",
         ("Paper & board", "Incineration with energy recovery"): "03050000030002",
         ("Paper & board", "Composting"): "03050000030003", ("Paper & board", "Landfill"): "03050000030004",
         ("Textiles & fabric offcuts", "Landfill"): "03050000040001",
         ("Textiles & fabric offcuts", "Recycling"): "03050000040002",
         ("Textiles & fabric offcuts", "Incineration"): "03050000040003"}
WASTE_TYPES = ["Commercial & industrial waste (mixed)", "Plastics", "Paper & board", "Textiles & fabric offcuts",
               "Sludge (ETP)", "Chemical containers", "Other waste"]
TREATMENTS = ["Reuse", "Recycling", "Composting", "Incineration with energy recovery", "Incineration", "Landfill",
              "Treatment", "Other"]
TERMINALS.append(terminal(
    "s3_c05", 3, "3.5", "Waste generated in operations",
    "All waste leaving your facilities, by type and treatment route. This data also drives the Waste module "
    "(totals, hazardous split and recycling rate).",
    "Wastewater volumes go in the Water module. Waste from sold products after use goes in 3.12.",
    "One row per waste type, treatment route, contractor and period, from waste manifests or weighbridge records. "
    "Mark hazardous waste.",
    "s3.c05",
    [facility(), *period(), supplier("Waste contractor / destination", True),
     enum("waste_type", "Waste type", WASTE_TYPES), enum("treatment", "Treatment method", TREATMENTS),
     enum("hazardous", "Hazardous", ["Yes", "No"]), qty("Quantity"), unit(["kg", "t"]),
     basis({"Weighbridge / manifest": "A", "Contractor estimate": "B", "Estimate": "C"}), NOTES],
    ["waste_type", "treatment"], {"Weighbridge / manifest": "A", "Contractor estimate": "B", "Estimate": "C"},
    [{**MASS_ONLY, "problem": "Waste is entered by mass", "fix": "Enter kg or tonnes."}], "waste_generated", 35,
    canonical={"mass": "kg"}))
for (wt, tr), code in WASTE.items():
    RULES.append({"terminal_key": "s3_c05", "match": {"waste_type": wt.casefold(), "treatment": tr.casefold()},
                  "taxonomy_code": code, "priority": 100, "note": None})

TRAVEL = {"Flight, economy": ("03060000010002", ["pkm"]), "Flight, business class": ("03060000010003", ["pkm"]),
          "Flight, class unknown": ("03060000010001", ["pkm"]), "Car (own or rental)": ("03060000020001", ["km", "mile"]),
          "Taxi": ("03060000020002", ["pkm"]), "Bus": ("03060000020003", ["pkm"]),
          "Rail": ("03060000020004", ["pkm"]), "Motorbike": ("03060000020005", ["km", "mile"]),
          "Hotel stay, Bangladesh": ("03060000030001", ["room_night"]),
          "Hotel stay, India": ("03060000030002", ["room_night"]), "Hotel stay, China": ("03060000030003", ["room_night"]),
          "Hotel stay, Vietnam": ("03060000030004", ["room_night"]),
          "Hotel stay, United Arab Emirates": ("03060000030005", ["room_night"]),
          "Hotel stay, Singapore": ("03060000030006", ["room_night"]),
          "Hotel stay, Thailand": ("03060000030007", ["room_night"])}
TERMINALS.append(terminal(
    "s3_c06", 3, "3.6", "Business travel",
    "Employee travel for work in vehicles the company does not own: flights, rail, bus, taxi, rental cars, and "
    "hotel nights.",
    "Company-owned vehicles go in Scope 1 mobile combustion. Daily commuting goes in 3.7.",
    "Flights, rail, bus and taxi: passenger-km (distance × travellers). Cars and motorbikes: vehicle-km. Hotels: "
    "room-nights.",
    "s3.c06",
    [facility(), *period(), supplier("Travel agency / provider"), enum("travel_mode", "Travel mode", list(TRAVEL)),
     qty("Quantity"), unit(["pkm", "km", "mile", "room_night"]), basis(STD_BASIS), NOTES],
    ["travel_mode"], STD_BASIS,
    [{"type": "unit_by_value", "column": "travel_mode", "allowed": {k: v[1] for k, v in TRAVEL.items()}}],
    "business_travel", 36, canonical={"distance": "km"}))
rules_for("s3_c06", "travel_mode", {k: v[0] for k, v in TRAVEL.items()})

COMMUTE = {"Car": ("03070000010001", ["km", "mile"]), "Motorbike": ("03070000010002", ["km", "mile"]),
           "Bus": ("03070000010003", ["pkm"]), "Rail": ("03070000010004", ["pkm"])}
TERMINALS.append(terminal(
    "s3_c07", 3, "3.7", "Employee commuting",
    "Employees' travel between home and work in vehicles the company does not own.",
    "Company-provided transport in company vehicles is Scope 1 mobile combustion.",
    "Totals per mode and period from a commuting survey: vehicle-km for cars and motorbikes, passenger-km for bus "
    "and rail.",
    "s3.c07",
    [facility(), *period(), enum("mode", "Commuting mode", list(COMMUTE)), qty("Quantity"),
     unit(["km", "mile", "pkm"]), basis({"Survey of all employees": "B", "Sample survey (extrapolated)": "C",
                                         "Estimate": "C"}), NOTES],
    ["mode"], {"Survey of all employees": "B", "Sample survey (extrapolated)": "C", "Estimate": "C"},
    [{"type": "unit_by_value", "column": "mode", "allowed": {k: v[1] for k, v in COMMUTE.items()}}],
    "employee_commuting", 37, canonical={"distance": "km"}))
rules_for("s3_c07", "mode", {k: v[0] for k, v in COMMUTE.items()})


def energy_category(key, no, name, root, description, excludes, mapping, sort, activity):
    TERMINALS.append(terminal(
        key, 3, no, name, description, excludes,
        "One row per asset (or site), energy type and period, from bills or the operator's statement.", root,
        [facility(), *period(), supplier("Operator / site"),
         enum("energy_type", "Energy type", list(mapping)), qty("Quantity"),
         unit(sorted({u for _, us in mapping.values() for u in us})), basis(STD_BASIS), NOTES],
        ["energy_type"], STD_BASIS,
        [{"type": "unit_by_value", "column": "energy_type", "allowed": {k: v[1] for k, v in mapping.items()}}],
        activity, sort))
    rules_for(key, "energy_type", {k: v[0] for k, v in mapping.items()})


energy_category("s3_c08", "3.8", "Upstream leased assets", "s3.c08",
                "Energy used in assets you lease (as tenant) that is not already in your Scope 1 and 2.",
                "If the leased space's energy is on your own bills, report it in Scope 1/2 instead.",
                {"Grid electricity": ("03080000010001", ["kWh", "MWh"]), "Natural gas": ("03080000010002", ["m3"])},
                38, "leased_assets_upstream")

FREIGHT_DOWN = {"Truck (HGV)": "03090000010001", "Van (diesel)": "03090000010002", "Container ship": "03090000010003"}
TERMINALS.append(terminal(
    "s3_c09", 3, "3.9", "Downstream transportation and distribution",
    "Transport of sold products to customers in vehicles you do not own or pay for.",
    "Transport you pay for belongs in 3.4 (upstream).", "Tonne-km per mode (tonnes shipped × distance).", "s3.c09",
    [facility(), *period(), supplier("Carrier"), enum("transport_mode", "Transport mode", list(FREIGHT_DOWN)),
     qty("Tonne-km"), unit(["tkm"]), basis(STD_BASIS), NOTES],
    ["transport_mode"], STD_BASIS, [], "downstream_transport", 39))
rules_for("s3_c09", "transport_mode", FREIGHT_DOWN)

energy_category("s3_c10", "3.10", "Processing of sold products", "s3.c10",
                "Energy used by third parties to further process intermediate products you sold.",
                None, {"Grid electricity": ("03100000010001", ["kWh", "MWh"]), "Natural gas": ("03100000010002", ["m3"])},
                40, "processing_sold_products")
energy_category("s3_c11", "3.11", "Use of sold products", "s3.c11",
                "Energy consumed or fuel burned by your sold products during their use.", None,
                {"Electricity consumed in use": ("03110000010001", ["kWh", "MWh"]),
                 "Diesel combusted in use": ("03110000010002", ["L", "m3", "t"])}, 41, "use_sold_products")

EOL = {"Mixed product waste, landfill": "03120000010001", "Plastic packaging, landfill": "03120000010002",
       "Paper packaging, recycling": "03120000010003", "Textiles, landfill": "03120000010004"}
TERMINALS.append(terminal(
    "s3_c12", 3, "3.12", "End-of-life treatment of sold products",
    "Disposal of the products and packaging you sold, at the end of their life.", None,
    "Estimated tonnes of product and packaging by disposal route.", "s3.c12",
    [facility(), *period(), enum("material_route", "Material and route", list(EOL)), qty("Quantity"), unit(["kg", "t"]),
     basis(STD_BASIS), NOTES],
    ["material_route"], STD_BASIS, [{**MASS_ONLY, "problem": "End-of-life is entered by mass", "fix": "Enter kg or tonnes."}],
    "end_of_life", 42, canonical={"mass": "kg"}))
rules_for("s3_c12", "material_route", EOL)

energy_category("s3_c13", "3.13", "Downstream leased assets", "s3.c13",
                "Energy used in assets you own and lease to others, not already in your Scope 1 and 2.", None,
                {"Grid electricity": ("03130000010001", ["kWh", "MWh"]), "Natural gas": ("03130000010002", ["m3"])},
                43, "leased_assets_downstream")
energy_category("s3_c14", "3.14", "Franchises", "s3.c14",
                "Energy used by franchises operating under your brand.", None,
                {"Grid electricity": ("03140000010001", ["kWh", "MWh"]), "Natural gas": ("03140000010002", ["m3"]),
                 "Diesel": ("03140000010003", ["L", "m3", "t"])}, 44, "franchises")

TERMINALS.append(terminal(
    "s3_c15", 3, "3.15", "Investments",
    "Emissions of companies and projects you invest in (equity, debt, project finance).",
    "The attribution method (e.g. PCAF) is pending the domain advisor; calculations show UNKNOWN until it is "
    "configured.", "One row per investment with the amount outstanding at period end.", "s3.c15",
    [facility(), *period(), supplier("Investee"), enum("investment_type", "Investment type",
                                                       ["Equity", "Corporate debt", "Project finance"]),
     qty("Amount outstanding"), unit(SPEND_UNITS), basis(SPEND_BASIS), NOTES],
    ["investment_type"], SPEND_BASIS, [CURRENCY_ONLY], "investments", 45, default_grade="C",
    canonical={"currency": "BDT"}))
rules_for("s3_c15", "investment_type", {"Equity": "03150000010001", "Corporate debt": "03150000010001",
                                        "Project finance": "03150000010001"})


def main() -> None:
    out = ROOT / "terminals"
    out.mkdir(exist_ok=True)
    keys = set()
    for t in TERMINALS:
        keys.add(t["key"])
        (out / f"{t['key']}.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n")
    for stale in out.glob("*.json"):
        if stale.stem not in keys and not stale.stem.startswith(("energy_", "water_")):
            stale.unlink()
    (ROOT / "lib" / "categorization_rules.json").write_text(json.dumps(RULES, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(TERMINALS)} terminals, {len(RULES)} categorization rules")


if __name__ == "__main__":
    main()
