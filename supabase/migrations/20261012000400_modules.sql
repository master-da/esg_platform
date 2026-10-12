-- =============================================================================
-- Environment & people modules (PRD Features 8-13) and the metric library (F14 B).
-- Energy, water and waste quantities live in public.activity_records (common data model);
-- this migration adds the module-specific structures around them.
-- =============================================================================

-- Manual single-row entries are stored like a one-row upload so statuses work uniformly.
alter table public.uploaded_files drop constraint uploaded_files_kind_check;
alter table public.uploaded_files add constraint uploaded_files_kind_check check (kind in ('template', 'bill', 'manual'));
alter table public.uploaded_files alter column storage_path drop not null;

-- File status also covers module terminals (energy/water), which have no categorization step:
-- their rows are confirmed by a person instead.
create or replace view public.v_file_status with (security_invoker = true) as
with recs as (
  select r.file_id,
         count(*) as records,
         count(*) filter (where cc.status = 'CALCULATED') as calculated,
         count(*) filter (where cc.status in ('UNKNOWN_FACTOR', 'UNIT_ERROR')) as errors,
         count(*) filter (where r.review_status = 'USER_VERIFIED') as verified,
         max(cc.calculated_at) as last_calc_at
  from public.activity_records r
  left join public.v_current_calcs cc on cc.activity_record_id = r.id
  where r.deleted_at is null and r.file_id is not null
  group by r.file_id
), last_review as (
  select distinct on (file_id) file_id, action, comment, reviewed_at, reviewed_by
  from public.file_reviews order by file_id, id desc
)
select f.id as file_id, f.company_id, f.project_id, f.terminal_key, f.kind, f.original_name, f.uploaded_at,
       f.uploaded_by, f.row_count, f.validation_passed,
       coalesce(recs.records, 0) as records, coalesce(recs.calculated, 0) as calculated,
       coalesce(recs.errors, 0) as calc_errors, recs.last_calc_at,
       lr.action as last_review_action, lr.comment as last_review_comment, lr.reviewed_at as last_reviewed_at,
       case
         when not f.validation_passed then 'NEED_ATTENTION'
         when f.kind = 'bill' and coalesce(recs.records, 0) = 0 then 'AWAITING_CONFIRMATION'
         when t.module <> 'ghg' then
           case when recs.records > 0 and recs.verified = recs.records then 'CONFIRMED' else 'AWAITING_CONFIRMATION' end
         when coalesce(recs.errors, 0) > 0 then 'NEED_ATTENTION'
         when lr.action = 'reject' and lr.reviewed_at >= coalesce(recs.last_calc_at, '-infinity') then 'NEED_ATTENTION'
         when recs.records > 0 and recs.calculated = recs.records and lr.action = 'confirm'
              and lr.reviewed_at >= recs.last_calc_at then 'CALCULATED'
         when recs.records > 0 and recs.calculated = recs.records then 'PRELIMINARY'
         else 'READY_TO_CATEGORIZE'
       end as status
from public.uploaded_files f
join ref.terminals t on t.key = f.terminal_key
left join recs on recs.file_id = f.id
left join last_review lr on lr.file_id = f.id
where f.deleted_at is null;
grant select on public.v_file_status to authenticated, engine_app;

-- -----------------------------------------------------------------------------
-- Metric library (F14 B) - reused across dashboards, reports and requirements.
-- -----------------------------------------------------------------------------
create table ref.metrics (
  key text primary key,
  name text not null,
  unit text,
  module text not null,
  description text not null,
  formula text,
  params jsonb not null default '{}',
  sort int not null default 0
);

-- -----------------------------------------------------------------------------
-- Energy intensity denominators (F8): user-defined per project and facility (null = whole company).
-- -----------------------------------------------------------------------------
create table public.denominators (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  facility_id uuid references public.facilities(id) on delete cascade,
  kind text not null check (kind in ('employees', 'production_mass', 'production_units', 'revenue')),
  value numeric not null check (value > 0),
  unit text not null,
  note text,
  updated_at timestamptz not null default now(),
  updated_by uuid default auth.uid()
);
create unique index denominators_one_per_scope on public.denominators
  (project_id, coalesce(facility_id, '00000000-0000-0000-0000-000000000000'::uuid), kind);
create trigger denominators_touch before update on public.denominators for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Water quality / ETP (F10): limits live in the database, versioned; never in frontend code.
-- -----------------------------------------------------------------------------
create table ref.wq_parameters (
  key text primary key,
  name text not null,
  unit text not null,
  sort int not null default 0
);

create table ref.wq_thresholds (
  id uuid primary key default gen_random_uuid(),
  parameter_key text not null references ref.wq_parameters(key),
  destination text,                     -- receiving environment; null = any
  sector_code text references ref.sectors(code),   -- null = all sectors
  min_value numeric,
  max_value numeric,
  -- Platform policy (not regulatory): a result within this % of a limit is flagged WARNING.
  warning_band_pct numeric not null default 10 check (warning_band_pct >= 0 and warning_band_pct < 100),
  regulator text not null,
  regulation text not null,
  source_url text not null,
  status text not null default 'NEEDS_REVIEW' check (status in ('VERIFIED', 'NEEDS_REVIEW')),
  valid_from date not null,
  valid_to date,
  version int not null default 1,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  check (min_value is not null or max_value is not null)
);

create table public.wq_samples (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  facility_id uuid not null references public.facilities(id),
  sample_date date not null,
  parameter_key text not null references ref.wq_parameters(key),
  value numeric not null,
  destination text,
  lab_name text,
  lab_report_ref text,
  -- computed by trigger from the threshold valid on the sample date
  result text check (result in ('PASS', 'WARNING', 'FAIL', 'NO_THRESHOLD')),
  threshold_id uuid references ref.wq_thresholds(id),
  threshold_snapshot jsonb,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
create index wq_samples_facility on public.wq_samples(company_id, facility_id, sample_date);

create or replace function app.evaluate_wq_sample() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  th ref.wq_thresholds;
  v_sector text;
  band numeric;
begin
  select c.sector_code into v_sector from public.companies c where c.id = new.company_id;
  select t.* into th from ref.wq_thresholds t
   where t.parameter_key = new.parameter_key
     and t.valid_from <= new.sample_date and (t.valid_to is null or t.valid_to >= new.sample_date)
     and (t.destination is null or t.destination = new.destination)
     and (t.sector_code is null or t.sector_code = v_sector)
   order by (t.destination is not null) desc, (t.sector_code is not null) desc, t.version desc
   limit 1;
  if th.id is null then
    new.result := 'NO_THRESHOLD';
    new.threshold_id := null;
    new.threshold_snapshot := null;
    return new;
  end if;
  new.threshold_id := th.id;
  new.threshold_snapshot := to_jsonb(th);
  band := th.warning_band_pct / 100.0;
  if (th.max_value is not null and new.value > th.max_value)
     or (th.min_value is not null and new.value < th.min_value) then
    new.result := 'FAIL';
  elsif (th.max_value is not null and new.value >= th.max_value - abs(th.max_value) * band)
     or (th.min_value is not null and new.value <= th.min_value + abs(th.min_value) * band) then
    new.result := 'WARNING';
  else
    new.result := 'PASS';
  end if;
  return new;
end $$;
create trigger wq_samples_evaluate before insert or update of value, parameter_key, sample_date, destination
  on public.wq_samples for each row execute function app.evaluate_wq_sample();

-- -----------------------------------------------------------------------------
-- Labour (F12): aggregated monthly figures only - no individual employee records.
-- -----------------------------------------------------------------------------
create table public.labour_monthly (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  facility_id uuid not null references public.facilities(id),
  month date not null check (extract(day from month) = 1),
  headcount_permanent int not null check (headcount_permanent >= 0),
  headcount_temporary int not null default 0 check (headcount_temporary >= 0),
  headcount_female int not null check (headcount_female >= 0),
  headcount_male int not null check (headcount_male >= 0),
  headcount_other int not null default 0 check (headcount_other >= 0),
  new_hires int not null default 0 check (new_hires >= 0),
  departures int not null default 0 check (departures >= 0),
  working_hours numeric check (working_hours >= 0),
  overtime_hours numeric check (overtime_hours >= 0),
  training_hours numeric check (training_hours >= 0),
  updated_at timestamptz not null default now(),
  updated_by uuid default auth.uid(),
  unique (facility_id, month),
  constraint labour_breakdowns_agree check (
    headcount_permanent + headcount_temporary = headcount_female + headcount_male + headcount_other)
);
create trigger labour_touch before update on public.labour_monthly for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Health & safety incidents (F13). No names or personal identifiers are stored.
-- -----------------------------------------------------------------------------
create table public.incidents (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  facility_id uuid not null references public.facilities(id),
  occurred_on date not null,
  type text not null check (type in ('injury', 'fatality', 'near_miss', 'fire', 'chemical', 'environmental', 'other')),
  severity text not null check (severity in ('minor', 'moderate', 'major', 'critical')),
  workers_affected int not null default 0 check (workers_affected >= 0),
  lost_time boolean not null default false,
  lost_days int not null default 0 check (lost_days >= 0),
  fatalities int not null default 0 check (fatalities >= 0),
  root_cause text,
  description text,
  status text not null default 'open' check (status in ('open', 'closed')),
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  check (type <> 'fatality' or fatalities > 0),
  check (lost_time or lost_days = 0)
);
create index incidents_company_date on public.incidents(company_id, occurred_on);

-- -----------------------------------------------------------------------------
-- Auditing, RLS, grants
-- -----------------------------------------------------------------------------
create trigger audit_denominators after insert or update or delete on public.denominators for each row execute function app.audit_row();
create trigger audit_wq_samples after insert or update or delete on public.wq_samples for each row execute function app.audit_row();
create trigger audit_wq_thresholds after insert or update or delete on ref.wq_thresholds for each row execute function app.audit_row();
create trigger audit_wq_parameters after insert or update or delete on ref.wq_parameters for each row execute function app.audit_row();
create trigger audit_labour after insert or update or delete on public.labour_monthly for each row execute function app.audit_row();
create trigger audit_incidents after insert or update or delete on public.incidents for each row execute function app.audit_row();
create trigger audit_metrics after insert or update or delete on ref.metrics for each row execute function app.audit_row();

alter table public.denominators enable row level security;
alter table public.wq_samples enable row level security;
alter table public.labour_monthly enable row level security;
alter table public.incidents enable row level security;

do $$
declare t text;
begin
  foreach t in array array['denominators', 'wq_samples', 'labour_monthly', 'incidents'] loop
    execute format('create policy %1$s_select on public.%1$s for select to authenticated using (app.can_read(company_id))', t);
    execute format('create policy %1$s_insert on public.%1$s for insert to authenticated with check (app.can_write(company_id))', t);
    execute format('create policy %1$s_update on public.%1$s for update to authenticated using (app.can_write(company_id)) with check (app.can_write(company_id))', t);
    execute format('create policy %1$s_delete on public.%1$s for delete to authenticated using (app.can_write(company_id))', t);
    execute format('grant select, insert, update, delete on public.%1$s to authenticated, engine_app', t);
  end loop;
end $$;

grant select on ref.metrics, ref.wq_parameters, ref.wq_thresholds to authenticated;
grant select, insert, update, delete on ref.metrics, ref.wq_parameters, ref.wq_thresholds to engine_app;
grant execute on function app.evaluate_wq_sample() to authenticated, engine_app;
