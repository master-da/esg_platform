import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import type { ProjectListItem } from "@/lib/types";
import { ExportWizard, type ReportRow } from "./export-wizard";

export default async function ReportsPage() {
  const ctx = await requireCompany();
  const supabase = await createClient();
  const [projects, frameworks, company, history] = await Promise.all([
    engineGet<ProjectListItem[]>(`/companies/${ctx.activeCompany.id}/projects`),
    supabase.schema("ref").from("frameworks").select("key, name, description").order("sort"),
    supabase.from("companies").select("fiscal_year_start, fiscal_year_end").eq("id", ctx.activeCompany.id).single(),
    engineGet<ReportRow[]>(`/companies/${ctx.activeCompany.id}/reports`),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Home" }, { label: "Reports & exports" }]} title="Export data and reports"
        description="Choose what to export, the period, and the data and format. Missing or estimated data is flagged before anything is exported." />
      <ExportWizard projects={projects} frameworks={frameworks.data ?? []} fiscal={company.data ?? { fiscal_year_start: "01-01", fiscal_year_end: "12-31" }} history={history} />
    </>
  );
}
