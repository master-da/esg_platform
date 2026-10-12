"""Generate reference-data/lib/taxonomy_nodes.csv from the tree below.

Code layout follows the PRD's 14-digit example (provisional, open item in the PRD):
  SS CC BBBBBB F S NN  -> scope, category, sub-branch, class, sub-class, item
  e.g. Stationary combustion 01010000000000 > Non-renewable 01010000001000 > Liquid 01010000001200
       > Petrol 01010000001201
Paths are ltree slugs used for roll-ups; names are the description path users see.
Run: python reference-data/sources/build_taxonomy.py
"""
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "lib" / "taxonomy_nodes.csv"

def n(code, slug, name, children=(), cat=None):
    return {"code": code, "slug": slug, "name": name, "children": list(children), "cat": cat}

def leaves(prefix, items):
    """prefix: first 12 digits; items: [(slug, name)] -> codes prefix+01, +02 ..."""
    return [n(f"{prefix}{i:02d}", s, nm) for i, (s, nm) in enumerate(items, start=1)]

TREE = [
  n("01000000000000", "s1", "Scope 1", [
    n("01010000000000", "stationary", "Stationary combustion", cat="1.2", children=[
      n("01010000001000", "nonrenewable", "Non-renewable fuels", [
        n("01010000001100", "gaseous", "Gaseous", leaves("010100000011", [
          ("natural_gas", "Natural gas"), ("lpg", "LPG"), ("cng", "CNG")])),
        n("01010000001200", "liquid", "Liquid", leaves("010100000012", [
          ("petrol", "Petrol"), ("diesel", "Diesel"), ("fuel_oil", "Fuel oil (furnace oil)"),
          ("kerosene", "Kerosene (burning oil)"), ("gas_oil", "Gas oil")])),
        n("01010000001300", "solid", "Solid", leaves("010100000013", [("coal_industrial", "Coal (industrial)")])),
      ]),
    ]),
    n("01020000000000", "mobile", "Mobile combustion", cat="1.3", children=[
      n("01020000010000", "road", "Road", leaves("010200000100", [
        ("diesel", "Diesel"), ("petrol", "Petrol (octane)"), ("cng", "CNG"), ("lpg", "LPG")])),
    ]),
    n("01030000000000", "fugitive", "Fugitive emissions", cat="1.1", children=[
      n("01030000010000", "refrigerants", "Refrigerants & air-conditioning", leaves("010300000100", [
        ("hfc_134a", "HFC-134a"), ("hfc_32", "HFC-32 (R-32)"), ("r_410a", "R-410A"),
        ("r_404a", "R-404A"), ("r_407c", "R-407C")])),
    ]),
  ]),
  n("02000000000000", "s2", "Scope 2", [
    n("02010000000000", "electricity", "Purchased electricity", cat="2.1", children=[
      n("02010000010000", "grid", "Grid electricity (location-based)", leaves("020100000100", [("national", "National grid")])),
    ]),
    n("02020000000000", "heating", "Purchased heating", cat="2.2", children=leaves("020200000100", [("purchased_heat", "Purchased heat")])),
    n("02030000000000", "steam", "Purchased steam", cat="2.3", children=leaves("020300000100", [("purchased_steam", "Purchased steam")])),
    n("02040000000000", "cooling", "Purchased cooling", cat="2.4", children=leaves("020400000100", [("purchased_cooling", "Purchased cooling / chilled water")])),
  ]),
  n("03000000000000", "s3", "Scope 3", [
    n("03990000000000", "spend", "Spend-based", cat="3.0", children=[
      n("03990000010000", "textiles", "Textile & apparel inputs", leaves("039900000100", [
        ("broadwoven_fabric", "Broadwoven fabric"), ("knit_fabric", "Knit fabric"),
        ("textile_finishing", "Textile & fabric finishing services"), ("apparel_cmt", "Cut-and-sew apparel")])),
      n("03990000020000", "chemicals", "Chemicals", leaves("039900000200", [
        ("dyes_pigments", "Synthetic dyes & pigments"), ("basic_organic", "Basic organic chemicals"),
        ("misc_chemicals", "Other chemical products")])),
      n("03990000030000", "packaging", "Packaging", leaves("039900000300", [
        ("corrugated_boxes", "Corrugated & solid fibre boxes"), ("plastic_bags", "Plastic bags & pouches"),
        ("plastic_products", "Other plastic products")])),
      n("03990000040000", "services", "Services", leaves("039900000400", [
        ("engineering", "Engineering services"), ("consulting", "Management consulting"),
        ("temp_staff", "Temporary staffing"), ("cleaning", "Cleaning & janitorial"), ("insurance", "Property & casualty insurance")])),
      n("03990000050000", "logistics", "Transport & logistics services", leaves("039900000500", [
        ("trucking", "Freight trucking"), ("freight_forwarding", "Freight forwarding & arrangement")])),
    ]),
    n("03010000000000", "c01", "Purchased goods and services", cat="3.1", children=[
      n("03010000010000", "materials", "Materials (by mass)", leaves("030100000100", [
        ("clothing", "Clothing / finished textiles"), ("plastics", "Plastics (average)"),
        ("paper_board", "Paper & board (mixed)"), ("metal_cans", "Metal (mixed cans)")])),
    ]),
    n("03020000000000", "c02", "Capital goods", cat="3.2", children=[
      n("03020000010000", "spend", "Spend-based", leaves("030200000100", [
        ("machinery", "Industrial machinery"), ("computers", "Computers & IT hardware"),
        ("buildings", "Commercial building construction")])),
    ]),
    n("03030000000000", "c03", "Fuel- and energy-related activities", cat="3.3", children=[
      n("03030000010000", "wtt_fuels", "Well-to-tank, fuels", leaves("030300000100", [
        ("natural_gas", "Natural gas"), ("diesel", "Diesel"), ("petrol", "Petrol"),
        ("fuel_oil", "Fuel oil"), ("lpg", "LPG"), ("cng", "CNG")])),
    ]),
    n("03040000000000", "c04", "Upstream transportation and distribution", cat="3.4", children=[
      n("03040000010000", "freight", "Freight", leaves("030400000100", [
        ("hgv_all", "Truck (HGV, all diesel, average laden)"), ("van_diesel", "Van (diesel, up to 3.5 t)"),
        ("container_ship", "Container ship (average)")])),
    ]),
    n("03050000000000", "c05", "Waste generated in operations", cat="3.5", children=[
      n("03050000010000", "commercial_industrial", "Commercial & industrial waste", leaves("030500000100", [
        ("landfill", "Landfill"), ("incineration_er", "Incineration with energy recovery")])),
      n("03050000020000", "plastics", "Plastics (average)", leaves("030500000200", [
        ("landfill", "Landfill"), ("recycled_closed", "Recycling (closed-loop)"), ("incineration_er", "Incineration with energy recovery")])),
      n("03050000030000", "paper_board", "Paper & board (mixed)", leaves("030500000300", [
        ("recycled_closed", "Recycling (closed-loop)"), ("incineration_er", "Incineration with energy recovery"),
        ("composting", "Composting"), ("landfill", "Landfill")])),
      n("03050000040000", "textiles", "Textiles & fabric offcuts", leaves("030500000400", [
        ("landfill", "Landfill"), ("recycled", "Recycling"), ("incineration", "Incineration")])),
    ]),
    n("03060000000000", "c06", "Business travel", cat="3.6", children=[
      n("03060000010000", "air", "Air", leaves("030600000100", [
        ("intl_average", "International flight, average passenger"), ("intl_economy", "International flight, economy"),
        ("intl_business", "International flight, business class")])),
      n("03060000020000", "land", "Land", leaves("030600000200", [
        ("car_average", "Car (average, unknown fuel)"), ("taxi", "Taxi"), ("bus", "Bus"),
        ("rail", "Rail"), ("motorbike", "Motorbike (average)")])),
      n("03060000030000", "hotel", "Hotel stay", leaves("030600000300", [
        ("bangladesh", "Hotel stay, Bangladesh"), ("india", "Hotel stay, India"), ("china", "Hotel stay, China"),
        ("vietnam", "Hotel stay, Vietnam"), ("uae", "Hotel stay, United Arab Emirates"),
        ("singapore", "Hotel stay, Singapore"), ("thailand", "Hotel stay, Thailand")])),
    ]),
    n("03070000000000", "c07", "Employee commuting", cat="3.7", children=[
      n("03070000010000", "modes", "Commuting modes", leaves("030700000100", [
        ("car_average", "Car (average, unknown fuel)"), ("motorbike", "Motorbike (average)"),
        ("bus", "Bus"), ("rail", "Rail")])),
    ]),
    n("03080000000000", "c08", "Upstream leased assets", cat="3.8", children=leaves("030800000100", [
        ("grid_electricity", "Grid electricity"), ("natural_gas", "Natural gas")])),
    n("03090000000000", "c09", "Downstream transportation and distribution", cat="3.9", children=[
      n("03090000010000", "freight", "Freight", leaves("030900000100", [
        ("hgv_all", "Truck (HGV, all diesel, average laden)"), ("van_diesel", "Van (diesel, up to 3.5 t)"),
        ("container_ship", "Container ship (average)")])),
    ]),
    n("03100000000000", "c10", "Processing of sold products", cat="3.10", children=leaves("031000000100", [
        ("grid_electricity", "Grid electricity used in processing"), ("natural_gas", "Natural gas used in processing")])),
    n("03110000000000", "c11", "Use of sold products", cat="3.11", children=leaves("031100000100", [
        ("grid_electricity", "Electricity consumed by products in use"), ("diesel", "Diesel combusted by products in use")])),
    n("03120000000000", "c12", "End-of-life treatment of sold products", cat="3.12", children=leaves("031200000100", [
        ("ci_landfill", "Mixed product waste, landfill"), ("plastics_landfill", "Plastic packaging, landfill"),
        ("paper_recycled", "Paper packaging, recycling (closed-loop)"), ("textiles_landfill", "Textiles, landfill")])),
    n("03130000000000", "c13", "Downstream leased assets", cat="3.13", children=leaves("031300000100", [
        ("grid_electricity", "Grid electricity"), ("natural_gas", "Natural gas")])),
    n("03140000000000", "c14", "Franchises", cat="3.14", children=leaves("031400000100", [
        ("grid_electricity", "Grid electricity"), ("natural_gas", "Natural gas"), ("diesel", "Diesel")])),
    n("03150000000000", "c15", "Investments", cat="3.15", children=leaves("031500000100", [
        ("investee_emissions", "Investee emissions (method pending)")])),
  ]),
]

def walk(node, parent_code, parent_path, scope, cat, rows, sort):
    path = f"{parent_path}.{node['slug']}" if parent_path else node["slug"]
    cat = node["cat"] or cat
    scope = scope or int(node["code"][:2])
    rows.append({"code": node["code"], "parent_code": parent_code or "", "path": path, "name": node["name"],
                 "scope": scope, "ghg_category": cat or "", "is_leaf": "true" if not node["children"] else "false",
                 "sort": sort})
    for i, child in enumerate(node["children"]):
        walk(child, node["code"], path, scope, cat, rows, i)

rows = []
for i, root in enumerate(TREE):
    walk(root, None, None, None, None, rows, i)
codes = [r["code"] for r in rows]
assert len(codes) == len(set(codes)), "duplicate code"
assert all(len(c) == 14 and c.isdigit() for c in codes)
with OUT.open("w", newline="") as fh:
    fh.write("# Provisional factor-code taxonomy (PRD Feature 6). Generated by sources/build_taxonomy.py.\n")
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} nodes, {sum(r['is_leaf'] == 'true' for r in rows)} leaves -> {OUT}")
