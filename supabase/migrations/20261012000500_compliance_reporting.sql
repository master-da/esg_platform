-- =============================================================================
-- Compliance, reporting & dashboards (PRD Features 14, 15, 16).
-- =============================================================================

-- A. Regulatory requirements: data, with applicability rules as data (no if/else in code).
create table ref.regulatory_requirements (
  id uuid primary key default gen_random_uuid(),
  code text not null,
  version int not null default 1,
  regulator text not null check (length(trim(regulator)) > 0),
  law text not null check (length(trim(law)) > 0),
  title text not null,
  description text,
  frequency text,
  required_metric_key text references ref.metrics(key),
  required_document text,
  source_url text not null check (source_url ~ '^https?://'),
  effective_date date not null,
  effective_until date,
  applicability_conditions jsonb not null default '{"all": []}',
  applies_universally boolean not null default false,
  status text not null default 'NEEDS_REVIEW' check (status in ('VERIFIED', 'NEEDS_REVIEW')),
  review_note text,
  created_at timestamptz not null default now(),
  unique (code, version)
);

-- B. Frameworks and metric mappings: a new framework is new rows, not new code.
create table ref.frameworks (
  key text primary key,
  name text not null,
  version text,
  description text,
  source_url text,
  sort int not null default 0
);

create table ref.framework_metric_mappings (
  framework_key text not null references ref.frameworks(key),
  metric_key text not null references ref.metrics(key),
  disclosure_ref text not null,
  disclosure_title text,
  sort int not null default 0,
  primary key (framework_key, metric_key, disclosure_ref)
);

create table public.company_frameworks (
  company_id uuid not null references public.companies(id) on delete cascade,
  framework_key text not null references ref.frameworks(key),
  selected_by uuid default auth.uid(),
  selected_at timestamptz not null default now(),
  primary key (company_id, framework_key)
);

-- F15. Permits & licences with configurable reminder lead time.
create table public.permits (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  facility_id uuid references public.facilities(id),
  permit_type text not null,
  permit_number text,
  issuing_authority text not null,
  issue_date date,
  expiry_date date,
  conditions text,
  reminder_lead_days int not null default 60 check (reminder_lead_days between 0 and 730),
  status text not null default 'active' check (status in ('active', 'renewal_in_progress', 'expired', 'cancelled')),
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_at timestamptz not null default now(),
  check (expiry_date is null or issue_date is null or expiry_date >= issue_date)
);
create trigger permits_touch before update on public.permits for each row execute function app.touch_updated_at();

-- C. Assumptions Register (feeds the report's assumptions & limitations section).
create table public.assumptions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  category text not null check (category in ('boundary', 'methodology', 'data', 'estimate', 'exclusion', 'other')),
  statement text not null check (length(trim(statement)) > 0),
  created_by uuid default auth.uid() constraint assumptions_created_by_fkey references public.profiles(user_id),
  created_at timestamptz not null default now()
);

-- Third-party verification: the only basis on which a report may say "verified" (PRD General Note 6).
create table public.verifications (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  verifier text not null,
  standard text not null,
  assurance_level text not null check (assurance_level in ('limited', 'reasonable')),
  statement_date date not null,
  scope text not null,
  recorded_by uuid default auth.uid(),
  recorded_at timestamptz not null default now()
);

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid references public.projects(id) on delete cascade,
  export_type text not null,
  format text not null check (format in ('xlsx', 'csv', 'pdf')),
  period_start date not null,
  period_end date not null,
  params jsonb not null default '{}',
  warnings jsonb not null default '[]',
  calc_version_ids uuid[] not null default '{}',
  storage_path text,
  file_name text not null,
  generated_by uuid default auth.uid(),
  generated_at timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
create trigger audit_requirements after insert or update or delete on ref.regulatory_requirements for each row execute function app.audit_row();
create trigger audit_frameworks after insert or update or delete on ref.frameworks for each row execute function app.audit_row();
create trigger audit_mappings after insert or update or delete on ref.framework_metric_mappings for each row execute function app.audit_row();
create trigger audit_company_frameworks after insert or update or delete on public.company_frameworks for each row execute function app.audit_row();
create trigger audit_permits after insert or update or delete on public.permits for each row execute function app.audit_row();
create trigger audit_assumptions after insert or update or delete on public.assumptions for each row execute function app.audit_row();
create trigger audit_verifications after insert or update or delete on public.verifications for each row execute function app.audit_row();
create trigger guard_assumptions before insert or update or delete on public.assumptions for each row execute function app.guard_project_data();

alter table public.company_frameworks enable row level security;
alter table public.permits enable row level security;
alter table public.assumptions enable row level security;
alter table public.verifications enable row level security;
alter table public.reports enable row level security;

create policy cf_select on public.company_frameworks for select to authenticated using (app.can_read(company_id));
create policy cf_insert on public.company_frameworks for insert to authenticated with check (app.can_manage(company_id));
create policy cf_delete on public.company_frameworks for delete to authenticated using (app.can_manage(company_id));

do $$
declare t text;
begin
  foreach t in array array['permits', 'assumptions'] loop
    execute format('create policy %1$s_select on public.%1$s for select to authenticated using (app.can_read(company_id))', t);
    execute format('create policy %1$s_insert on public.%1$s for insert to authenticated with check (app.can_write(company_id))', t);
    execute format('create policy %1$s_update on public.%1$s for update to authenticated using (app.can_write(company_id)) with check (app.can_write(company_id))', t);
    execute format('create policy %1$s_delete on public.%1$s for delete to authenticated using (app.can_write(company_id))', t);
    execute format('grant select, insert, update, delete on public.%1$s to authenticated', t);
  end loop;
end $$;

-- Verifications are recorded by internal users only, so a company cannot self-declare assurance.
create policy verifications_select on public.verifications for select to authenticated using (app.can_read(company_id));
create policy verifications_insert on public.verifications for insert to authenticated with check ((select app.is_internal()));
create policy verifications_delete on public.verifications for delete to authenticated using ((select app.is_platform_admin()));
create policy reports_select on public.reports for select to authenticated using (app.can_read(company_id));

grant select, insert, delete on public.company_frameworks, public.verifications to authenticated;
grant select on public.reports to authenticated;
grant select on ref.regulatory_requirements, ref.frameworks, ref.framework_metric_mappings to authenticated;
grant select, insert, update, delete on ref.regulatory_requirements, ref.frameworks, ref.framework_metric_mappings to engine_app;
grant select, insert, update, delete on public.company_frameworks, public.permits, public.assumptions, public.verifications,
  public.reports to engine_app;
