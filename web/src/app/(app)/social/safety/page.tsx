import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { engineGet } from "@/lib/engine-server";
import { projectsAndSelection } from "@/lib/projects";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { SafetyView, type SafetyData } from "./safety-view";

export default async function SafetyPage(props: PageProps<"/social/safety">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const { selected, options } = await projectsAndSelection(ctx.activeCompany.id, sp.project);
  const facilities = (await (await createClient()).from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).eq("is_company_level", false).order("name")).data ?? [];
  const data = selected ? await engineGet<SafetyData>(`/companies/${ctx.activeCompany.id}/safety?start=${selected.start_date}&end=${selected.end_date}`) : null;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Social" }, { label: "Health & safety" }]}
        title="Health & safety"
        description="Incidents, lost-time injuries and frequency rates. Hours worked come from the Labour module."
        actions={options.length > 0 && <ProjectPicker projects={options} selected={selected?.id} />}
      />
      {data ? <SafetyView data={data} companyId={ctx.activeCompany.id} facilities={facilities} canWrite={canWrite(ctx)} /> :
        <p className="text-sm text-muted-foreground">Create a project to choose the reporting period.</p>}
    </>
  );
}
