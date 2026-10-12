# ESG & Carbon Compliance Platform (MVP)

A carbon accounting and ESG compliance platform for companies in Bangladesh, built from
[`PRD_Crbn_Acc_Pltfrm_v01.md`](PRD_Crbn_Acc_Pltfrm_v01.md). It covers PRD Phases 1–6
(Features 1–16 and 18). Feature 17, the AI Assistant, is Phase 7 in the PRD and is not built.

The rules the whole system follows:

- **Deterministic numbers.** Every figure comes from `calculate_emissions()` in Python (`Decimal`), never from an AI model.
- **Traceability.** Every number drills down to its calculation, record, file and row, and to the factor's source, in two clicks or fewer.
- **Versioning.** Factors, regulations and calculations are versioned. A LOCKED project's results never change silently.
- **No fabrication.** Unknown values show as UNKNOWN, Missing or NEEDS_REVIEW, never as 0. Seeded reference data is real and cited, or it is left out.
- **Isolation.** Reference data is kept apart from customer data. Tenants are isolated by Postgres RLS. The audit log is append-only and visible to internal users only. Factor codes never reach clients.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Database | Postgres 17 on **Supabase** (local via CLI + Docker), with `ltree` and `btree_gist` | RLS for tenant isolation. `ltree` for taxonomy roll-ups. EXCLUDE constraints stop overlapping active factors and overlapping project periods. `numeric` stores exact quantities. |
| Auth and files | Supabase Auth (email/password, invite, reset) and a private Supabase Storage bucket | Required by the PRD. Only the engine touches storage. |
| Engine | **Python 3.13 + FastAPI**, psycopg 3, `decimal.Decimal`, openpyxl, ReportLab, PyJWT | The PRD names a Python calculation engine. Decimal arithmetic makes results reproducible. |
| AI | `AIProvider` interface: Claude (`claude-opus-5-5`, structured output) or `NullProvider` | Used only for bill extraction and categorization suggestions, and a person always confirms. Without an API key the platform runs on rules and manual entry alone. |
| Web | **Next.js 16** (App Router), React 19, Tailwind 4, shadcn/ui, Recharts, `@supabase/ssr` | Data-dense tables, side panels and charts, as in the wireframes. |
| Tooling | uv, npm, Supabase CLI, Make, pytest, Playwright, ruff, ESLint | |

## Quick start

Prerequisites: Docker Desktop (running), the Supabase CLI (`brew install supabase/tap/supabase`),
[uv](https://docs.astral.sh/uv/), and Node.js 20.9 or newer.

```bash
cd engine && uv sync && cd ../web && npm install && cd ..

make up       # start local Supabase and write engine/.env + web/.env.local
make reset    # apply migrations, load cited reference data, create dev users
make demo     # optional: two demo projects (FY 2025, FY 2026) for Sample Textiles Ltd

make engine   # engine API on http://localhost:8000 (OpenAPI docs at /docs)
make web      # web app on http://localhost:3000   (separate terminal)
```

Invite and password-reset emails land in Mailpit at <http://127.0.0.1:54324>.

**Optional AI.** Add `ANTHROPIC_API_KEY=...` to `engine/.env` and restart the engine. `make env`
keeps the key when it regenerates the file. Without a key:
- electricity bills use a manual review form
- categorization suggestions come from rules only

### Dev users

All dev users share the password `Password123!`. They exist only in the local database.

| Email | Role | Company |
|---|---|---|
| `admin@platform.test` | Platform admin (can edit the factor library) | internal |
| `reviewer@platform.test` | Internal user (confirms or rejects files) | internal |
| `a.rahman@sample.test` | Company admin | Sample Textiles Ltd |
| `s.akter@sample.test` | Sustainability manager (approves and locks) | Sample Textiles Ltd |
| `f.manager@sample.test`, `t.islam@sample.test` | Facility manager, data entry | Sample Textiles Ltd |
| `auditor@sample.test`, `viewer@sample.test` | Auditor, viewer (read-only) | Sample Textiles Ltd |
| `admin@other.test` | Company admin | Other Garments Ltd (tenant isolation checks) |

## Repository layout

```
supabase/          config.toml, migrations (schema, RLS, triggers), auth email templates
reference-data/    cited reference data + build scripts (see reference-data/README.md)
engine/            FastAPI engine: calc/, ingest/, categorize/, ai/, services/, reports/, compliance/, api/
web/               Next.js app: src/app/(app)/{home,environmental,social,governance,settings,internal}
scripts/gen-env.sh writes local env files from `supabase status`
```

## Architecture

**Schemas**
- `public` holds customer data. Every business table carries `company_id` and has RLS enabled.
- `ref` holds read-only reference data that clients may see: units, terminals, metrics, frameworks, regulations, and the code-free `taxonomy_labels`.
- `lib` holds the factor library (taxonomy codes, emission factors, conversions, FX rates, categorization rules). It is not exposed through PostgREST and is reachable only through engine endpoints.
- `app` holds private helper functions (RBAC checks, audit triggers, guards).

Supabase's default grants are revoked, then granted table by table. Tests check grants, RLS, and that the OpenAPI document contains no `factor_code`.

**Data path**
- **Direct reads and plain CRUD.** The web app reads through Supabase under RLS. It does plain CRUD directly only on descriptive data: company and facility fields, tasks, notes, permits, incidents, labour, water-quality samples, denominators and assumptions.
- **Through the engine.** Anything that leads to a number goes through the engine: uploads, validation, categorization, calculations, file confirmations, recalculation, exports, invites, role changes, library edits and stage changes.

**Engine transactions.** The engine connects as `engine_app` (BYPASSRLS, NOINHERIT member of `authenticated`). It verifies the user's JWT (JWKS or HS256), sets `request.jwt.claims`, then runs `SET LOCAL ROLE authenticated`, so permission checks and reads run under RLS. It drops back with `RESET ROLE` only for the privileged write. The claims stay set, so audit triggers record the real user.

**Pipeline**
1. Each of the 26 upload *terminals* is configuration (`reference-data/terminals/*.json`). The configuration defines columns, dropdowns, units, validation rules and quality grades. Templates carry a hidden `_meta` sheet, so a file uploaded to the wrong category is rejected with the correct category's name.
2. A file with errors creates no records. The issues list each row, field, problem and fix.
3. Categorization runs rules first, then AI within the terminal's own taxonomy subtree. Nothing counts until a person accepts it, and acceptance makes the records `USER_VERIFIED`.
4. `calculate_emissions` resolves the factor as of the version's `library_as_of`, falling back from country to region to global. It converts units and multiplies in `Decimal`. The final kg CO2e is rounded once (6 dp, half-even). With no factor the result is `UNKNOWN_FACTOR`; with no unit path it is `UNIT_ERROR`; neither is ever 0.
5. `emission_calculations` is insert-only and snapshots the factor value, source, unit and conversion, but never the code.
6. File status is derived in a view (`v_file_status`), never stored. Only an internal reviewer's confirmation makes a file *Calculated*. Any later change sends it back to *Preliminary*.
7. Lock gate and recalculation. A project can't be approved or locked until every in-scope file is Calculated and nothing is UNKNOWN. Recalculating a LOCKED project needs explicit confirmation and creates version N+1; older versions are never changed.

**Missing, N/A and zero are different.** Coverage is computed per in-scope category × facility × month. A gap shows as *Missing*. A category marked out of scope shows *N/A* with its reason. An explicit 0 stays 0. A ratio with a missing input is Missing.

**Reports.** Framework layouts (GHG Protocol, GRI, CDP-style, Basic ESG) come from one generic exporter driven by `ref.framework_metric_mappings`. Adding a framework means adding rows, not code. Before export, the system warns about missing and estimated data.

The audit export carries everything needed to recompute each result, but no factor codes. The PDF report:
- is available only for APPROVED or LOCKED projects
- passes a wording guard that blocks "certified / audited / verified / assured" unless a third-party verification is recorded

**Compliance.** Regulatory requirements are data. Each carries its regulator, law, source URL and effective date, and applicability is a JSON condition the engine evaluates. Permit renewal alerts are computed when the page loads, using each permit's lead time.

## Testing

```bash
make test        # engine: unit + DB/RLS/API integration tests (needs `make up`)
make e2e         # Playwright golden path + bill flow (needs `make engine` and `make web`)
make lint        # ruff + ESLint
make typecheck   # tsc
```

Current status:
- 151 engine tests pass.
- 2 Playwright specs pass. The golden path runs create project → bad upload with per-row errors → good upload → accept categorizations → trail → internal confirm → approve and lock → audit Excel and PDF export.

Both suites remove the companies, users and projects they create.

The engine tests cover:
- Decimal determinism and the UNKNOWN / UNIT_ERROR paths
- a template round-trip for every terminal
- tenant isolation through both PostgREST and the engine
- role limits
- LOCKED guards and recalculation versions
- overlapping-factor and overlapping-period constraints
- audit-log immutability and visibility
- the ETP / LTIFR / turnover / recycling maths
- applicability rules
- the wording guard
- recomputing every GHG value from the audit export alone

## Known data limitations

- **No Bangladesh grid factor after June 2022.** The Department of Environment's official GEF covers FY2019-20 to FY2021-22 only, so Scope 2 electricity for later periods shows **UNKNOWN**. This is why the FY 2025 demo project stays in REVIEW.
- **No ECR 2023 effluent limits seeded.** They could not be verified from an official source. Internal users add limits, with their source, on the Water page. Until then, samples show `NO_THRESHOLD`.
- **Advisor review pending.** All seeded factors have `advisor_reviewed = false`, and all seeded regulations are `NEEDS_REVIEW`. Both are shown in the UI and in report limitations.
- **Spend-based Scope 3** uses US EPA v1.3 factors (2022 USD) at the cited annual BDT/USD rate, with no inflation adjustment.
- **Scope 2 is location-based only.**
- **Permit reminders appear in the app only.** There is no email or scheduled job.

Sources are listed in [reference-data/README.md](reference-data/README.md).

## Open items for the product owner

These are open in the PRD. Each is configurable, and none blocks the MVP.

- **Codes and templates**
  - The factor-code digit scheme (currently the PRD's 14-digit example).
  - Final template layouts and validation rules (all terminals are `0.x-provisional` configuration).
  - The Scope 3 Category 4 template (the terminal ships disabled) and the Category 15 attribution method.
- **Scope 2**
  - The terminal split: four terminals, following the navigation, while the PRD's terminal table groups heating, steam and cooling.
  - Location-based vs market-based reporting.
- **Roles and navigation**
  - License tiers.
  - Which roles may edit the factor library (currently platform admins plus internal users flagged `can_edit_library`).
  - Sub-sections under Social and Governance (placement is provisional).
- **Domain advisor review**
  - The seeded factors, regulations and thresholds.
  - A Bangladesh grid factor for periods after June 2022.
  - The ECR 2023 effluent limits.
