-- =============================================================================
-- Reference data & Emission Factor Library (PRD Feature 6).
--   ref.* : units, conversions, geographies, terminals, taxonomy labels (no codes)  -> clients may read
--   lib.* : taxonomy codes, emission factors, factor conversions, FX, categorization rules -> engine only
-- =============================================================================

create table ref.units (
  code text primary key,
  name text not null,
  dimension text not null check (dimension in ('mass', 'volume', 'energy', 'distance', 'passenger_distance',
    'freight_distance', 'currency', 'count', 'time', 'concentration', 'temperature', 'ph', 'area', 'ratio')),
  sort int not null default 0
);

-- Generic conversions WITHIN one dimension (exact unit definitions). Cross-dimension conversions
-- (litres -> kg, litres -> kWh) only come from a matched factor's own lib.factor_conversions.
create table ref.unit_conversions (
  from_unit text not null references ref.units(code),
  to_unit text not null references ref.units(code),
  multiplier numeric not null check (multiplier > 0),
  definition text not null,
  primary key (from_unit, to_unit)
);

create or replace function app.unit_conversion_same_dimension() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (select dimension from ref.units where code = new.from_unit)
     <> (select dimension from ref.units where code = new.to_unit) then
    raise exception 'Generic unit conversions must stay within one dimension (% -> %)', new.from_unit, new.to_unit;
  end if;
  return new;
end $$;
create trigger unit_conversions_same_dimension before insert or update on ref.unit_conversions
  for each row execute function app.unit_conversion_same_dimension();

create table ref.geographies (
  code text primary key,
  name text not null,
  level text not null check (level in ('country', 'region', 'global')),
  parent_code text references ref.geographies(code),
  country_code text references ref.countries(code)
);

-- -----------------------------------------------------------------------------
-- Factor-code taxonomy (codes are internal: lib only)
-- -----------------------------------------------------------------------------
create table lib.taxonomy_nodes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,                 -- factor code at this level (digit scheme is a PRD open item)
  parent_id uuid references lib.taxonomy_nodes(id),
  path extensions.ltree not null unique,     -- slug path for roll-ups, e.g. s1.stationary.nonrenewable.liquid.petrol
  name text not null,
  scope smallint not null check (scope in (1, 2, 3)),
  ghg_category text,                          -- e.g. 1.2, 2.1, 3.6 (navigation numbering)
  is_leaf boolean not null default false,
  sort int not null default 0
);
create index taxonomy_nodes_path_gist on lib.taxonomy_nodes using gist (path);

-- Client-safe view: description paths and roll-up paths, never codes.
create view ref.taxonomy_labels as
select n.id, n.path::text as path, n.name, n.scope, n.ghg_category, n.is_leaf, n.sort,
       (select string_agg(a.name, ' > ' order by extensions.nlevel(a.path))
          from lib.taxonomy_nodes a where a.path operator(extensions.@>) n.path) as display_path
from lib.taxonomy_nodes n;

-- -----------------------------------------------------------------------------
-- Emission factors
-- -----------------------------------------------------------------------------
create table lib.emission_factors (
  id uuid primary key default gen_random_uuid(),
  factor_code text not null,
  version int not null check (version >= 1),
  taxonomy_node_id uuid not null references lib.taxonomy_nodes(id),
  geography_code text not null references ref.geographies(code),
  activity_unit text not null references ref.units(code),
  -- kg CO2e per activity unit, total and per-gas contributions (gas rows are already in CO2e)
  co2e numeric not null check (co2e >= 0),
  co2e_co2 numeric,
  co2e_ch4 numeric,
  co2e_n2o numeric,
  gwp_version text not null,
  source_name text not null check (length(trim(source_name)) > 0),
  source_url text,
  source_year int not null,
  source_ref text,
  methodology text,
  quality_rating text,
  valid_from date not null,
  valid_to date not null,
  status text not null default 'draft' check (status in ('draft', 'active', 'retired')),
  activated_at timestamptz,
  retired_at timestamptz,
  advisor_reviewed boolean not null default false,
  notes text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  unique (factor_code, version),
  check (valid_to >= valid_from),
  -- PRD F6: two factors with overlapping validity for the same activity/geography cannot both be active.
  constraint emission_factors_no_overlapping_active exclude using gist (
    taxonomy_node_id with =, geography_code with =, daterange(valid_from, valid_to, '[]') with &&
  ) where (status = 'active')
);
create index emission_factors_node on lib.emission_factors(taxonomy_node_id, geography_code);

-- Active factors are immutable (a correction is a new version). Only retirement is allowed.
create or replace function app.emission_factor_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    if old.status <> 'draft' then
      raise exception 'Only draft factors can be deleted; retire factor % v% instead', old.factor_code, old.version;
    end if;
    return old;
  end if;
  if tg_op = 'INSERT' then
    if new.status = 'active' and new.activated_at is null then new.activated_at := now(); end if;
    return new;
  end if;
  if old.status = 'retired' and (to_jsonb(new) - 'notes') <> (to_jsonb(old) - 'notes') then
    raise exception 'Retired factor % v% cannot be changed', old.factor_code, old.version;
  end if;
  if old.status = 'active' then
    if (to_jsonb(new) - array['status', 'retired_at', 'advisor_reviewed', 'notes'])
       <> (to_jsonb(old) - array['status', 'retired_at', 'advisor_reviewed', 'notes']) then
      raise exception 'Active factor % v% is immutable; create a new version instead', old.factor_code, old.version;
    end if;
    if new.status = 'draft' then
      raise exception 'An active factor cannot return to draft';
    end if;
    if new.status = 'retired' and new.retired_at is null then new.retired_at := now(); end if;
  end if;
  if old.status = 'draft' and new.status = 'active' then
    new.activated_at := now();
  end if;
  return new;
end $$;
create trigger emission_factors_guard before insert or update or delete on lib.emission_factors
  for each row execute function app.emission_factor_guard();

create table lib.factor_conversions (
  id uuid primary key default gen_random_uuid(),
  emission_factor_id uuid not null references lib.emission_factors(id) on delete cascade,
  from_unit text not null references ref.units(code),
  to_unit text not null references ref.units(code),
  multiplier numeric not null check (multiplier > 0),
  source_name text not null,
  source_url text,
  note text,
  unique (emission_factor_id, from_unit, to_unit)
);

-- Conversions of an active or retired factor are part of that factor and equally immutable.
create or replace function app.factor_conversion_guard() returns trigger
language plpgsql set search_path = '' as $$
declare v_status text;
begin
  select status into v_status from lib.emission_factors
   where id = coalesce(new.emission_factor_id, old.emission_factor_id);
  if v_status <> 'draft' then
    if tg_op = 'UPDATE' and to_jsonb(new) = to_jsonb(old) then return new; end if;
    -- The reference-data loader may seed a cited factor's conversions, and re-run idempotently
    -- (an identical row then becomes a no-op ON CONFLICT update). A changed multiplier is rejected.
    if tg_op = 'INSERT' and current_setting('app.source', true) = 'refdata-loader'
       and not exists (select 1 from lib.factor_conversions c where c.emission_factor_id = new.emission_factor_id
                       and c.from_unit = new.from_unit and c.to_unit = new.to_unit
                       and c.multiplier <> new.multiplier) then
      return new;
    end if;
    raise exception 'Conversions of a % factor cannot be changed; create a new factor version', v_status;
  end if;
  return coalesce(new, old);
end $$;
create trigger factor_conversions_guard before insert or update or delete on lib.factor_conversions
  for each row execute function app.factor_conversion_guard();

create table lib.fx_rates (
  base_currency text not null references ref.units(code),
  quote_currency text not null references ref.units(code),
  year int not null,
  rate numeric not null check (rate > 0),   -- units of quote currency per 1 base currency
  source_name text not null,
  source_url text,
  primary key (base_currency, quote_currency, year)
);

-- -----------------------------------------------------------------------------
-- Upload terminals (one per scope/category; config-driven templates and validation)
-- -----------------------------------------------------------------------------
create table ref.terminals (
  key text primary key,
  module text not null check (module in ('ghg', 'energy', 'water', 'waste')),
  scope smallint check (scope in (1, 2, 3)),
  category_no text,                 -- navigation number, e.g. 1.3, 2.1, 3.6
  name text not null,
  description text not null,        -- what belongs here
  excludes text,                    -- what does not, and where it goes instead
  instructions text,
  taxonomy_root text,               -- ltree path of the taxonomy subtree used for categorization
  accepts_bills boolean not null default false,
  enabled boolean not null default true,
  disabled_reason text,
  template_version text not null,
  config jsonb not null,            -- columns, dropdowns, units, validation rules, categorization keys, grades
  sort int not null default 0
);

create table lib.categorization_rules (
  id uuid primary key default gen_random_uuid(),
  terminal_key text not null references ref.terminals(key),
  match jsonb not null,             -- {"fuel_type": "diesel"} matched against normalised input values
  taxonomy_code text not null references lib.taxonomy_nodes(code) on update cascade,
  priority int not null default 100,
  note text,
  unique (terminal_key, match)
);

-- -----------------------------------------------------------------------------
-- Auditing, RLS and grants
-- -----------------------------------------------------------------------------
create trigger audit_units after insert or update or delete on ref.units for each row execute function app.audit_row();
create trigger audit_unit_conversions after insert or update or delete on ref.unit_conversions for each row execute function app.audit_row();
create trigger audit_geographies after insert or update or delete on ref.geographies for each row execute function app.audit_row();
create trigger audit_terminals after insert or update or delete on ref.terminals for each row execute function app.audit_row();
create trigger audit_taxonomy after insert or update or delete on lib.taxonomy_nodes for each row execute function app.audit_row();
create trigger audit_emission_factors after insert or update or delete on lib.emission_factors for each row execute function app.audit_row();
create trigger audit_factor_conversions after insert or update or delete on lib.factor_conversions for each row execute function app.audit_row();
create trigger audit_fx_rates after insert or update or delete on lib.fx_rates for each row execute function app.audit_row();
create trigger audit_categorization_rules after insert or update or delete on lib.categorization_rules for each row execute function app.audit_row();

grant select on ref.units, ref.unit_conversions, ref.geographies, ref.terminals, ref.taxonomy_labels to authenticated;
grant select, insert, update, delete on ref.units, ref.unit_conversions, ref.geographies, ref.terminals to engine_app;
grant select on ref.taxonomy_labels to engine_app;
grant select, insert, update, delete on all tables in schema lib to engine_app;
