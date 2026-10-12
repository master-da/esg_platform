-- =============================================================================
-- Foundation: schemas, privileges, roles, tenancy, RBAC helpers, audit log.
-- PRD Features 1, 2, 18.
--
-- Schemas
--   public : customer (tenant) data. RLS on every table; every row has company_id.
--   ref    : reference data that clients may read (exposed via PostgREST, read-only).
--   lib    : emission factor library incl. factor codes. NOT exposed; engine only.
--   app    : private helper functions used by RLS policies and triggers.
-- =============================================================================

create extension if not exists ltree with schema extensions;
create extension if not exists btree_gist with schema extensions;

create schema if not exists app;
create schema if not exists ref;
create schema if not exists lib;

-- Supabase grants ALL on new public objects to anon/authenticated by default.
-- Nothing is exposed unless a later statement grants it explicitly.
alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated;
alter default privileges for role postgres revoke execute on functions from public;

-- The engine's database role. It is a member of `authenticated` (NOINHERIT) so it
-- can `SET LOCAL ROLE authenticated` to act under RLS as the calling user, and it
-- bypasses RLS only after `RESET ROLE` for writes it has already authorised.
-- Its password is set outside migrations (supabase/seed.sql locally, secret store in prod).
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'engine_app') then
    create role engine_app with login noinherit bypassrls;
  end if;
end $$;
grant authenticated to engine_app;

revoke all on schema lib from public, anon, authenticated;
revoke all on schema app from public, anon;
grant usage on schema app to authenticated, engine_app;
grant usage on schema ref to authenticated, engine_app;
grant usage on schema lib to engine_app;
grant usage on schema public to engine_app;
grant usage on schema extensions to engine_app;
-- auth.uid()/auth.jwt() are used for actor attribution while the engine acts privileged.
grant usage on schema auth to engine_app;
grant execute on function auth.uid(), auth.jwt(), auth.role() to engine_app;

-- -----------------------------------------------------------------------------
-- Generic helpers
-- -----------------------------------------------------------------------------
create or replace function app.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- -----------------------------------------------------------------------------
-- Controlled lists used by company / facility setup (reference data)
-- -----------------------------------------------------------------------------
create table ref.countries (
  code text primary key,                -- ISO 3166-1 alpha-2
  name text not null,
  default_currency text not null,
  default_timezone text not null
);

create table ref.currencies (
  code text primary key,                -- ISO 4217
  name text not null
);

create table ref.sectors (
  code text primary key,
  name text not null,
  parent_code text references ref.sectors(code),
  sort int not null default 0
);

create table ref.company_sizes (
  code text primary key,
  name text not null,
  sort int not null default 0
);

create table ref.facility_types (
  code text primary key,
  name text not null,
  sort int not null default 0
);

create table ref.environmental_classifications (
  code text primary key,
  name text not null,
  source_name text,
  source_url text,
  status text not null default 'NEEDS_REVIEW' check (status in ('VERIFIED', 'NEEDS_REVIEW')),
  sort int not null default 0
);

create table ref.org_categories (
  code text primary key,
  name text not null,
  requires_crm_record boolean not null default false
);

create table ref.license_tiers (
  code text primary key,
  name text not null,
  provisional boolean not null default true   -- tier names/limits pending the commercial model
);

-- -----------------------------------------------------------------------------
-- Identity: profiles, internal users, company memberships
-- -----------------------------------------------------------------------------
create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Platform-side staff. No client write path exists for this table.
create table public.internal_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  internal_role text not null check (internal_role in ('PLATFORM_ADMIN', 'INTERNAL_USER')),
  can_edit_library boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  created_by uuid
);

create table public.companies (
  id uuid primary key default gen_random_uuid(),
  company_id uuid generated always as (id) stored,   -- uniform tenancy column
  legal_name text not null,
  trading_name text,
  registration_number text,
  country_code text not null default 'BD' references ref.countries(code),
  address text,
  district text,
  city text,
  sector_code text references ref.sectors(code),
  sub_sector_code text references ref.sectors(code),
  company_size_code text references ref.company_sizes(code),
  reporting_currency text not null default 'BDT' references ref.currencies(code),
  fiscal_year_start text not null default '01-01' check (fiscal_year_start ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
  fiscal_year_end text not null default '12-31' check (fiscal_year_end ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
  timezone text not null default 'Asia/Dhaka',
  -- Organization metadata, maintained by internal users only (Settings > Organizations)
  org_category text not null default 'customer' references ref.org_categories(code),
  license_tier text references ref.license_tiers(code),
  sector_classification_code text,
  crm_record_id text,
  tax_vat_number text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_at timestamptz not null default now(),
  constraint companies_customer_needs_crm check (org_category <> 'customer' or crm_record_id is not null)
);
create unique index companies_company_id_key on public.companies(company_id);

create table public.memberships (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('COMPANY_ADMIN', 'SUSTAINABILITY_MANAGER', 'FACILITY_MANAGER',
                                     'DATA_ENTRY', 'AUDITOR', 'VIEWER')),
  status text not null default 'invited' check (status in ('invited', 'active', 'disabled')),
  invited_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, user_id)
);
create index memberships_user_idx on public.memberships(user_id);
-- Lets PostgREST embed the member's profile (profiles row is created with the auth user).
alter table public.memberships add constraint memberships_profile_fk
  foreign key (user_id) references public.profiles(user_id) on delete cascade;
alter table public.internal_users add constraint internal_users_profile_fk
  foreign key (user_id) references public.profiles(user_id) on delete cascade;

create table public.facilities (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  name text not null,
  facility_type text references ref.facility_types(code),
  address text,
  district text,
  city text,
  operational_status text not null default 'operating'
    check (operational_status in ('operating', 'under_construction', 'idle', 'closed')),
  environmental_classification text references ref.environmental_classifications(code),
  employee_count int check (employee_count >= 0),
  production_type text,
  production_unit text,
  production_quantity numeric check (production_quantity >= 0),
  -- One per company, auto-created: holds company-level data (travel, spend, ...) so every
  -- activity record has a facility and company totals = sum of facility totals.
  is_company_level boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, name)
);
create unique index facilities_one_company_level on public.facilities(company_id) where is_company_level;

create trigger companies_touch before update on public.companies
  for each row execute function app.touch_updated_at();
create trigger facilities_touch before update on public.facilities
  for each row execute function app.touch_updated_at();
create trigger memberships_touch before update on public.memberships
  for each row execute function app.touch_updated_at();
create trigger profiles_touch before update on public.profiles
  for each row execute function app.touch_updated_at();

create or replace function app.create_company_level_facility() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.facilities (company_id, name, facility_type, is_company_level)
  values (new.id, 'Company-level (all sites)', null, true);
  return new;
end $$;
create trigger companies_company_level_facility after insert on public.companies
  for each row execute function app.create_company_level_facility();

-- The company-level facility cannot be deleted or demoted.
create or replace function app.protect_company_level_facility() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' and old.is_company_level then
    -- allowed only when the whole company is being deleted (cascade)
    if exists (select 1 from public.companies c where c.id = old.company_id) then
      raise exception 'The company-level facility cannot be deleted.';
    end if;
    return old;
  end if;
  if tg_op = 'UPDATE' and old.is_company_level <> new.is_company_level then
    raise exception 'is_company_level cannot be changed.';
  end if;
  return coalesce(new, old);
end $$;
create trigger facilities_protect_company_level before update or delete on public.facilities
  for each row execute function app.protect_company_level_facility();

-- New auth user -> profile row
create or replace function app.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (user_id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name', null))
  on conflict (user_id) do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function app.handle_new_user();

-- -----------------------------------------------------------------------------
-- RBAC helpers (SECURITY DEFINER so policies can consult memberships without recursion)
-- -----------------------------------------------------------------------------
create or replace function app.is_internal() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.internal_users iu where iu.user_id = auth.uid() and iu.active)
$$;

create or replace function app.is_platform_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.internal_users iu
                 where iu.user_id = auth.uid() and iu.active and iu.internal_role = 'PLATFORM_ADMIN')
$$;

create or replace function app.can_edit_library() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.internal_users iu
                 where iu.user_id = auth.uid() and iu.active
                   and (iu.internal_role = 'PLATFORM_ADMIN' or iu.can_edit_library))
$$;

create or replace function app.my_company_ids() returns setof uuid
language sql stable security definer set search_path = '' as $$
  select m.company_id from public.memberships m where m.user_id = auth.uid() and m.status = 'active'
$$;

create or replace function app.company_role(p_company uuid) returns text
language sql stable security definer set search_path = '' as $$
  select m.role from public.memberships m
  where m.user_id = auth.uid() and m.company_id = p_company and m.status = 'active'
$$;

-- Read access: internal users see every company; external users see their own companies.
create or replace function app.can_read(p_company uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select app.is_internal() or app.company_role(p_company) is not null
$$;

-- Data work (upload, categorize, tasks, notes, module data). AUDITOR/VIEWER are read-only.
create or replace function app.can_write(p_company uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select app.is_internal()
      or app.company_role(p_company) in ('COMPANY_ADMIN', 'SUSTAINABILITY_MANAGER', 'FACILITY_MANAGER', 'DATA_ENTRY')
$$;

-- Company setup (facilities, frameworks, project settings).
create or replace function app.can_manage(p_company uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select app.is_internal() or app.company_role(p_company) in ('COMPANY_ADMIN', 'SUSTAINABILITY_MANAGER')
$$;

-- Approve / lock a project. DATA_ENTRY and FACILITY_MANAGER cannot.
create or replace function app.can_approve(p_company uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select app.is_platform_admin() or app.company_role(p_company) in ('COMPANY_ADMIN', 'SUSTAINABILITY_MANAGER')
$$;

-- Invite / manage users of a company.
create or replace function app.can_admin_users(p_company uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select app.is_platform_admin() or app.company_role(p_company) = 'COMPANY_ADMIN'
$$;

grant execute on function app.is_internal(), app.is_platform_admin(), app.can_edit_library(),
  app.my_company_ids(), app.company_role(uuid), app.can_read(uuid), app.can_write(uuid),
  app.can_manage(uuid), app.can_approve(uuid), app.can_admin_users(uuid)
  to authenticated, engine_app;

-- -----------------------------------------------------------------------------
-- Audit log (Feature 18): immutable, internal-only.
-- -----------------------------------------------------------------------------
create table public.audit_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  actor_user_id uuid,                -- null = system
  source text not null default 'web',-- web (PostgREST) | engine | system
  company_id uuid,                   -- null for global reference/library data
  entity text not null,
  entity_id text,
  action text not null,              -- INSERT/UPDATE/DELETE or an event (UPLOAD, CALCULATE, APPROVE, ...)
  old_value jsonb,
  new_value jsonb,
  detail jsonb
);
create index audit_log_company_at on public.audit_log(company_id, at desc);
create index audit_log_entity on public.audit_log(entity, entity_id);

create or replace function app.audit_source() returns text
language sql stable set search_path = '' as $$
  select coalesce(nullif(current_setting('app.source', true), ''), 'web')
$$;

create or replace function app.audit_row() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_old jsonb;
  v_new jsonb;
  v_company uuid;
  v_id text;
begin
  if tg_op in ('UPDATE', 'DELETE') then v_old := to_jsonb(old); end if;
  if tg_op in ('UPDATE', 'INSERT') then v_new := to_jsonb(new); end if;
  if tg_op = 'UPDATE' and v_old = v_new then
    return new;
  end if;
  v_company := coalesce((v_new->>'company_id')::uuid, (v_old->>'company_id')::uuid);
  v_id := coalesce(v_new->>'id', v_old->>'id', v_new->>'user_id', v_old->>'user_id',
                   v_new->>'code', v_old->>'code', v_new->>'key', v_old->>'key');
  insert into public.audit_log (actor_user_id, source, company_id, entity, entity_id, action, old_value, new_value)
  values (auth.uid(), app.audit_source(), v_company, tg_table_schema || '.' || tg_table_name, v_id, tg_op, v_old, v_new);
  return coalesce(new, old);
end $$;

-- Explicit business events (upload, calculate, approve, reject, lock, report-generate ...).
create or replace function app.log_event(p_company uuid, p_entity text, p_entity_id text,
                                         p_action text, p_detail jsonb default null)
returns void language sql security definer set search_path = '' as $$
  insert into public.audit_log (actor_user_id, source, company_id, entity, entity_id, action, detail)
  values (auth.uid(), app.audit_source(), p_company, p_entity, p_entity_id, p_action, p_detail)
$$;
grant execute on function app.log_event(uuid, text, text, text, jsonb) to engine_app;

create or replace function app.audit_log_immutable() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'audit_log is append-only: % is not allowed', tg_op;
end $$;
create trigger audit_log_no_update before update or delete on public.audit_log
  for each row execute function app.audit_log_immutable();
create trigger audit_log_no_truncate before truncate on public.audit_log
  for each statement execute function app.audit_log_immutable();

-- Attach row-level auditing to master data.
create trigger audit_companies after insert or update or delete on public.companies
  for each row execute function app.audit_row();
create trigger audit_facilities after insert or update or delete on public.facilities
  for each row execute function app.audit_row();
create trigger audit_memberships after insert or update or delete on public.memberships
  for each row execute function app.audit_row();
create trigger audit_internal_users after insert or update or delete on public.internal_users
  for each row execute function app.audit_row();
create trigger audit_profiles after update or delete on public.profiles
  for each row execute function app.audit_row();

-- -----------------------------------------------------------------------------
-- Row-level security
-- -----------------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.internal_users enable row level security;
alter table public.companies enable row level security;
alter table public.memberships enable row level security;
alter table public.facilities enable row level security;
alter table public.audit_log enable row level security;

-- profiles: self, people in my companies, or internal
create policy profiles_select on public.profiles for select to authenticated using (
  user_id = auth.uid()
  or (select app.is_internal())
  or exists (select 1 from public.memberships m
             where m.user_id = profiles.user_id and m.company_id in (select app.my_company_ids()))
);
create policy profiles_update_self on public.profiles for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- internal_users: visible to internal users and to the user themself. No client writes.
create policy internal_users_select on public.internal_users for select to authenticated
  using (user_id = auth.uid() or (select app.is_internal()));

create policy companies_select on public.companies for select to authenticated
  using ((select app.is_internal()) or id in (select app.my_company_ids()));
create policy companies_update on public.companies for update to authenticated
  using (app.can_manage(id)) with check (app.can_manage(id));

create policy memberships_select on public.memberships for select to authenticated
  using (user_id = auth.uid() or app.can_read(company_id));

create policy facilities_select on public.facilities for select to authenticated
  using (app.can_read(company_id));
create policy facilities_insert on public.facilities for insert to authenticated
  with check (app.can_manage(company_id) and not is_company_level);
create policy facilities_update on public.facilities for update to authenticated
  using (app.can_manage(company_id)) with check (app.can_manage(company_id));
create policy facilities_delete on public.facilities for delete to authenticated
  using (app.can_manage(company_id) and not is_company_level);

create policy audit_log_select on public.audit_log for select to authenticated
  using ((select app.is_internal()));

-- -----------------------------------------------------------------------------
-- Grants (explicit; defaults were revoked above)
-- -----------------------------------------------------------------------------
grant select on all tables in schema ref to authenticated;
grant select, insert, update, delete on all tables in schema ref to engine_app;

grant select on public.profiles, public.internal_users, public.companies, public.memberships,
  public.facilities, public.audit_log to authenticated;
grant update (full_name) on public.profiles to authenticated;
-- Company profile fields editable by company managers; org metadata only via the engine.
grant update (legal_name, trading_name, registration_number, country_code, address, district, city,
  sector_code, sub_sector_code, company_size_code, reporting_currency, fiscal_year_start,
  fiscal_year_end, timezone) on public.companies to authenticated;
grant insert, update, delete on public.facilities to authenticated;

grant select, insert, update, delete on public.profiles, public.internal_users, public.companies,
  public.memberships, public.facilities to engine_app;
grant select on public.audit_log to engine_app;

-- -----------------------------------------------------------------------------
-- Session context for the web app
-- -----------------------------------------------------------------------------
create or replace function public.my_context() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'user_id', auth.uid(),
    'email', (select p.email from public.profiles p where p.user_id = auth.uid()),
    'full_name', (select p.full_name from public.profiles p where p.user_id = auth.uid()),
    'internal_role', (select iu.internal_role from public.internal_users iu where iu.user_id = auth.uid() and iu.active),
    'can_edit_library', app.can_edit_library(),
    'memberships', coalesce((
      select jsonb_agg(jsonb_build_object('company_id', m.company_id, 'company_name', c.legal_name,
                                          'role', m.role, 'status', m.status) order by c.legal_name)
      from public.memberships m join public.companies c on c.id = m.company_id
      where m.user_id = auth.uid() and m.status in ('active', 'invited')), '[]'::jsonb)
  )
$$;
grant execute on function public.my_context() to authenticated;

-- Invited users activate their memberships on first password set.
create or replace function public.accept_invitations() returns void
language sql security definer set search_path = '' as $$
  update public.memberships set status = 'active'
  where user_id = auth.uid() and status = 'invited'
$$;
grant execute on function public.accept_invitations() to authenticated;
