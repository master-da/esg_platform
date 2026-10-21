-- List every category in every open project, including ones whose upload template is not available yet
-- (Scope 3 Category 4). They are added as not applicable with the terminal's reason, matching what
-- POST /projects now does. Approved and locked projects are left untouched.
insert into public.project_categories (company_id, project_id, terminal_key, in_scope, na_reason)
select p.company_id, p.id, t.key, false, coalesce(t.disabled_reason, 'Not available yet')
from public.projects p
cross join ref.terminals t
where not t.enabled
  and p.stage not in ('APPROVED', 'LOCKED')
on conflict (project_id, terminal_key) do nothing;
