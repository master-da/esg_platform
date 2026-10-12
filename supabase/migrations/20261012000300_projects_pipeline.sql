-- =============================================================================
-- Projects, data intake and the calculation pipeline (PRD Features 3, 4, 5, 5.1, 5.2, 6, 7).
-- Pipeline tables are written only by the engine; clients have SELECT under RLS.
-- =============================================================================

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  name text not null,
  period_type text not null check (period_type in ('year', 'half_year', 'quarter')),
  start_date date not null,
  end_date date not null,
  boundary text not null default 'organization' check (boundary in ('organization', 'division')),
  division_name text,
  boundary_key text generated always as (
    case when boundary = 'organization' then 'organization' else 'division:' || lower(coalesce(division_name, '')) end
  ) stored,
  upload_deadline date,
  stage text not null default 'DRAFT'
    check (stage in ('DRAFT', 'DATA_COLLECTION', 'REVIEW', 'APPROVED', 'LOCKED')),
  current_version_id uuid,
  locked_at timestamptz,
  locked_by uuid,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_at timestamptz not null default now(),
  check (end_date >= start_date),
  check (boundary = 'organization' or nullif(trim(division_name), '') is not null),
  -- No double counting: one project per company/boundary for any given day.
  constraint projects_no_overlap exclude using gist (
    company_id with =, boundary_key with =, daterange(start_date, end_date, '[]') with &&
  )
);
create trigger projects_touch before update on public.projects for each row execute function app.touch_updated_at();

create table public.calculation_versions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  version_no int not null,
  library_as_of timestamptz not null default now(),   -- factor resolution is pinned to this library snapshot
  reason text not null,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  frozen_at timestamptz,
  unique (project_id, version_no)
);
alter table public.projects add constraint projects_current_version_fk
  foreign key (current_version_id) references public.calculation_versions(id);

-- Which categories (upload terminals) are in scope for the project, with assignee (PRD F3).
create table public.project_categories (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  terminal_key text not null references ref.terminals(key),
  in_scope boolean not null default true,
  na_reason text,
  assignee_id uuid references public.profiles(user_id),
  unique (project_id, terminal_key),
  check (in_scope or nullif(trim(na_reason), '') is not null)
);

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  terminal_key text references ref.terminals(key),
  kind text not null default 'collection' check (kind in ('collection', 'factor_request', 'review')),
  title text not null,
  description text,
  assignee_id uuid references public.profiles(user_id),
  due_date date,
  status text not null default 'open' check (status in ('open', 'done')),
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table public.notes (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  terminal_key text references ref.terminals(key),
  body text not null check (length(trim(body)) > 0),
  author_id uuid default auth.uid() references public.profiles(user_id),
  created_at timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- Intake
-- -----------------------------------------------------------------------------
create table public.uploaded_files (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  terminal_key text not null references ref.terminals(key),
  kind text not null default 'template' check (kind in ('template', 'bill')),
  original_name text not null,
  storage_path text not null,
  content_type text,
  size_bytes bigint,
  sha256 text,
  template_version text,
  validation_passed boolean not null default false,
  row_count int not null default 0,
  uploaded_by uuid default auth.uid(),
  uploaded_at timestamptz not null default now(),
  deleted_at timestamptz,
  deleted_by uuid
);
create index uploaded_files_project on public.uploaded_files(project_id, terminal_key);

create table public.validation_issues (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  file_id uuid not null references public.uploaded_files(id) on delete cascade,
  row_number int,
  field text,
  problem text not null,
  fix text,
  severity text not null default 'error' check (severity in ('error', 'warning'))
);
create index validation_issues_file on public.validation_issues(file_id);

-- Internal reviewer decisions (insert-only). The latest one per file counts.
create table public.file_reviews (
  id bigint generated always as identity primary key,
  company_id uuid not null references public.companies(id) on delete cascade,
  file_id uuid not null references public.uploaded_files(id) on delete cascade,
  action text not null check (action in ('confirm', 'reject')),
  comment text,
  calc_version_id uuid references public.calculation_versions(id),
  reviewed_by uuid default auth.uid(),
  reviewed_at timestamptz not null default now()
);

-- Common data model for all activity data (PRD F4). One structure, activity_type from configuration.
create table public.activity_records (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  facility_id uuid not null references public.facilities(id),
  terminal_key text not null references ref.terminals(key),
  activity_type text not null,
  file_id uuid references public.uploaded_files(id),
  source_row int,
  source_type text not null check (source_type in ('template_upload', 'bill_upload', 'manual_entry', 'api_sync')),
  supplier_name text,
  period_start date not null,
  period_end date not null,
  attributes jsonb not null default '{}',
  category_input_key text,                 -- normalised categorization key (GHG terminals)
  category_input jsonb,                    -- the original values of the categorization columns
  original_quantity numeric not null,
  original_unit text not null references ref.units(code),
  normalized_quantity numeric not null,
  normalized_unit text not null references ref.units(code),
  data_basis text,
  quality_grade text not null check (quality_grade in ('A', 'B', 'C')),
  review_status text not null default 'pending_review' check (review_status in ('pending_review', 'USER_VERIFIED')),
  verified_by uuid,
  verified_at timestamptz,
  entered_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  deleted_by uuid,
  check (period_end >= period_start)
);
create index activity_records_project on public.activity_records(project_id, terminal_key) where deleted_at is null;
create index activity_records_file on public.activity_records(file_id);

create table public.categorizations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  terminal_key text not null references ref.terminals(key),
  input_key text not null,
  input_display jsonb not null,
  status text not null default 'NEEDS' check (status in ('NEEDS', 'SUGGESTED', 'ACCEPTED')),
  suggested_node_id uuid references lib.taxonomy_nodes(id),
  suggested_by text check (suggested_by in ('rule', 'ai', 'user')),
  suggested_by_user uuid,
  suggested_at timestamptz,
  suggestion_note text,
  accepted_node_id uuid references lib.taxonomy_nodes(id),
  accepted_by uuid,
  accepted_at timestamptz,
  factor_requested_at timestamptz,
  unique (project_id, terminal_key, input_key),
  check (status <> 'ACCEPTED' or (accepted_node_id is not null and accepted_by is not null and accepted_at is not null))
);

create table public.bill_extractions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  file_id uuid not null unique references public.uploaded_files(id) on delete cascade,
  provider text not null,
  model text,
  status text not null default 'AI_EXTRACTED' check (status in ('AI_EXTRACTED', 'USER_VERIFIED', 'FAILED')),
  document_type text,
  extracted jsonb,                         -- candidate fields as returned by the AI provider
  confirmed jsonb,                         -- the values the user confirmed (may differ from extracted)
  error text,
  activity_record_id uuid references public.activity_records(id),
  created_at timestamptz not null default now(),
  confirmed_by uuid,
  confirmed_at timestamptz
);

-- -----------------------------------------------------------------------------
-- Calculations: insert-only, full snapshot, never overwritten (PRD F7). No factor codes stored.
-- -----------------------------------------------------------------------------
create table public.emission_calculations (
  id bigint generated always as identity primary key,
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  calc_version_id uuid not null references public.calculation_versions(id),
  activity_record_id uuid not null references public.activity_records(id),
  categorization_id uuid references public.categorizations(id),
  status text not null check (status in ('CALCULATED', 'UNKNOWN_FACTOR', 'UNIT_ERROR', 'VOID')),
  message text,
  taxonomy_node_id uuid,
  taxonomy_path extensions.ltree,
  taxonomy_display text,
  scope smallint,
  ghg_category text,
  emission_factor_id uuid,
  factor_value numeric,
  factor_unit text,
  factor_geography text,
  factor_source_name text,
  factor_source_url text,
  factor_source_year int,
  factor_version int,
  gwp_version text,
  conversion_from text,
  conversion_to text,
  conversion_multiplier numeric,
  conversion_kind text,
  conversion_source text,
  input_quantity numeric not null,
  input_unit text not null,
  factor_unit_quantity numeric,
  co2e_kg numeric,
  co2e_t numeric generated always as (co2e_kg / 1000) stored,
  co2_kg numeric,
  ch4_kg numeric,
  n2o_kg numeric,
  quality_grade text,
  formula text,
  engine_version text not null,
  calculated_at timestamptz not null default now(),
  calculated_by uuid default auth.uid(),
  check (status <> 'CALCULATED' or co2e_kg is not null)
);
create index emission_calculations_lookup on public.emission_calculations(calc_version_id, activity_record_id, id desc);
create index emission_calculations_path on public.emission_calculations using gist (taxonomy_path);

create or replace function app.insert_only() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception '% is insert-only: % is not allowed', tg_table_name, tg_op;
end $$;
create trigger emission_calculations_insert_only before update or delete on public.emission_calculations
  for each row execute function app.insert_only();
create trigger file_reviews_insert_only before update or delete on public.file_reviews
  for each row execute function app.insert_only();

-- Current result per record: latest row of the project's current calculation version.
create view public.v_current_calcs with (security_invoker = true) as
select distinct on (c.activity_record_id) c.*, r.facility_id, r.terminal_key, r.file_id, r.source_row,
       r.supplier_name, r.period_start, r.period_end
from public.emission_calculations c
join public.projects p on p.id = c.project_id and p.current_version_id = c.calc_version_id
join public.activity_records r on r.id = c.activity_record_id and r.deleted_at is null
order by c.activity_record_id, c.id desc;

-- File status is derived, never stored (PRD 5.1).
create view public.v_file_status with (security_invoker = true) as
with recs as (
  select r.file_id,
         count(*) as records,
         count(*) filter (where cc.status = 'CALCULATED') as calculated,
         count(*) filter (where cc.status in ('UNKNOWN_FACTOR', 'UNIT_ERROR')) as errors,
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
         when coalesce(recs.errors, 0) > 0 then 'NEED_ATTENTION'
         when lr.action = 'reject' and lr.reviewed_at >= coalesce(recs.last_calc_at, '-infinity') then 'NEED_ATTENTION'
         when recs.records > 0 and recs.calculated = recs.records and lr.action = 'confirm'
              and lr.reviewed_at >= recs.last_calc_at then 'CALCULATED'
         when recs.records > 0 and recs.calculated = recs.records then 'PRELIMINARY'
         else 'READY_TO_CATEGORIZE'
       end as status
from public.uploaded_files f
left join recs on recs.file_id = f.id
left join last_review lr on lr.file_id = f.id
where f.deleted_at is null;

-- -----------------------------------------------------------------------------
-- Stage guard: approved / locked projects' underlying data cannot change (PRD F3).
-- -----------------------------------------------------------------------------
create or replace function app.guard_project_data() returns trigger
language plpgsql set search_path = '' as $$
declare
  v_stage text;
  v_name text;
begin
  select p.stage, p.name into v_stage, v_name from public.projects p
   where p.id = coalesce(new.project_id, old.project_id);
  if v_stage = 'LOCKED' then
    raise exception 'Project "%" is LOCKED. Its data cannot be changed; corrections require an explicit recalculation that creates a new calculation version.', v_name
      using errcode = 'P0001', hint = 'locked';
  elsif v_stage = 'APPROVED' then
    raise exception 'Project "%" is APPROVED. Move it back to REVIEW before changing its data.', v_name
      using errcode = 'P0001', hint = 'approved';
  end if;
  return coalesce(new, old);
end $$;
create trigger guard_activity_records before insert or update or delete on public.activity_records
  for each row execute function app.guard_project_data();
create trigger guard_uploaded_files before insert or update or delete on public.uploaded_files
  for each row execute function app.guard_project_data();
create trigger guard_categorizations before insert or update or delete on public.categorizations
  for each row execute function app.guard_project_data();
create trigger guard_project_categories before insert or update or delete on public.project_categories
  for each row execute function app.guard_project_data();

create or replace function app.guard_project_row() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    if old.stage = 'LOCKED' then raise exception 'A LOCKED project cannot be deleted.'; end if;
    return old;
  end if;
  if old.stage = 'LOCKED' then
    if new.stage <> 'LOCKED' then
      raise exception 'Project "%" is LOCKED and cannot be reopened.', old.name;
    end if;
    -- boundary_key is a generated column: not yet computed in NEW inside a BEFORE trigger.
    if (to_jsonb(new) - array['current_version_id', 'updated_at', 'boundary_key'])
       <> (to_jsonb(old) - array['current_version_id', 'updated_at', 'boundary_key']) then
      raise exception 'Project "%" is LOCKED. Its settings cannot be changed.', old.name;
    end if;
  end if;
  return new;
end $$;
create trigger projects_guard before update or delete on public.projects
  for each row execute function app.guard_project_row();

-- -----------------------------------------------------------------------------
-- Auditing (row-level for master data and decisions; uploads/calculations log one event per action)
-- -----------------------------------------------------------------------------
create trigger audit_projects after insert or update or delete on public.projects for each row execute function app.audit_row();
create trigger audit_calc_versions after insert on public.calculation_versions for each row execute function app.audit_row();
create trigger audit_project_categories after insert or update or delete on public.project_categories for each row execute function app.audit_row();
create trigger audit_tasks after insert or update or delete on public.tasks for each row execute function app.audit_row();
create trigger audit_notes after insert or update or delete on public.notes for each row execute function app.audit_row();
create trigger audit_uploaded_files after update or delete on public.uploaded_files for each row execute function app.audit_row();
create trigger audit_file_reviews after insert on public.file_reviews for each row execute function app.audit_row();
create trigger audit_activity_records after update or delete on public.activity_records for each row execute function app.audit_row();
create trigger audit_categorizations after update or delete on public.categorizations for each row execute function app.audit_row();
create trigger audit_bill_extractions after insert or update on public.bill_extractions for each row execute function app.audit_row();

-- -----------------------------------------------------------------------------
-- RLS & grants
-- -----------------------------------------------------------------------------
alter table public.projects enable row level security;
alter table public.calculation_versions enable row level security;
alter table public.project_categories enable row level security;
alter table public.tasks enable row level security;
alter table public.notes enable row level security;
alter table public.uploaded_files enable row level security;
alter table public.validation_issues enable row level security;
alter table public.file_reviews enable row level security;
alter table public.activity_records enable row level security;
alter table public.categorizations enable row level security;
alter table public.bill_extractions enable row level security;
alter table public.emission_calculations enable row level security;

create policy read_projects on public.projects for select to authenticated using (app.can_read(company_id));
create policy read_versions on public.calculation_versions for select to authenticated using (app.can_read(company_id));
create policy read_project_categories on public.project_categories for select to authenticated using (app.can_read(company_id));
create policy read_tasks on public.tasks for select to authenticated using (app.can_read(company_id));
create policy read_notes on public.notes for select to authenticated using (app.can_read(company_id));
create policy read_files on public.uploaded_files for select to authenticated using (app.can_read(company_id));
create policy read_issues on public.validation_issues for select to authenticated using (app.can_read(company_id));
create policy read_reviews on public.file_reviews for select to authenticated using (app.can_read(company_id));
create policy read_records on public.activity_records for select to authenticated using (app.can_read(company_id));
create policy read_categorizations on public.categorizations for select to authenticated using (app.can_read(company_id));
create policy read_bills on public.bill_extractions for select to authenticated using (app.can_read(company_id));
create policy read_calcs on public.emission_calculations for select to authenticated using (app.can_read(company_id));

-- Tasks and notes are plain collaboration data, written directly by users who can write.
create policy write_tasks on public.tasks for insert to authenticated with check (app.can_write(company_id));
create policy update_tasks on public.tasks for update to authenticated using (app.can_write(company_id)) with check (app.can_write(company_id));
create policy delete_tasks on public.tasks for delete to authenticated using (app.can_write(company_id));
create policy write_notes on public.notes for insert to authenticated with check (app.can_write(company_id) and author_id = auth.uid());
create policy delete_notes on public.notes for delete to authenticated using (author_id = auth.uid());

grant select on public.projects, public.calculation_versions, public.project_categories, public.tasks, public.notes,
  public.uploaded_files, public.validation_issues, public.file_reviews, public.activity_records,
  public.categorizations, public.bill_extractions, public.emission_calculations,
  public.v_current_calcs, public.v_file_status to authenticated;
grant insert, update, delete on public.tasks to authenticated;
grant insert, delete on public.notes to authenticated;

grant select, insert, update, delete on public.projects, public.calculation_versions, public.project_categories,
  public.tasks, public.notes, public.uploaded_files, public.validation_issues, public.activity_records,
  public.categorizations, public.bill_extractions to engine_app;
grant select, insert on public.emission_calculations, public.file_reviews to engine_app;
grant select on public.v_current_calcs, public.v_file_status to engine_app;

-- Private storage bucket for uploads. No client policies: only the engine reads/writes and signs URLs.
insert into storage.buckets (id, name, public, file_size_limit)
values ('uploads', 'uploads', false, 26214400)
on conflict (id) do nothing;
