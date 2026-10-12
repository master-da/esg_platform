import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { InsightsView, type InsightsData } from "./insights-view";

export default async function InsightsPage(props: PageProps<"/home/insights">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const q = new URLSearchParams();
  for (const k of ["project", "facility", "grade", "path"] as const) {
    const v = sp[k];
    if (typeof v === "string" && v) q.set(k === "project" ? "project_id" : k === "facility" ? "facility_id" : k, v);
  }
  const supabase = await createClient();
  const [data, facilities, categories] = await Promise.all([
    engineGet<InsightsData>(`/companies/${ctx.activeCompany.id}/insights?${q}`),
    supabase.from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).order("is_company_level").order("name"),
    supabase.schema("ref").from("taxonomy_labels").select("path, name, ghg_category").like("path", "s3.%").not("path", "like", "s3.%.%").order("sort"),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Home" }, { label: "Insights" }]} title="Insights"
        description="Emissions by scope, source, facility and data quality. Every card and bar opens the calculations behind it." />
      <InsightsView data={data} companyId={ctx.activeCompany.id} facilities={facilities.data ?? []}
        categories={(categories.data ?? []) as never} filters={{ project: (sp.project as string) ?? "", facility: (sp.facility as string) ?? "", grade: (sp.grade as string) ?? "", path: (sp.path as string) ?? "" }} />
    </>
  );
}
