import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { engineGet } from "@/lib/engine-server";
import { projectsAndSelection } from "@/lib/projects";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { LabourView, type LabourData } from "./labour-view";

export default async function LabourPage(props: PageProps<"/social/labour">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const { selected, options } = await projectsAndSelection(ctx.activeCompany.id, sp.project);
  const facility = typeof sp.facility === "string" ? sp.facility : "";
  const facilities = (await (await createClient()).from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).eq("is_company_level", false).order("name")).data ?? [];
  const data = selected
    ? await engineGet<LabourData>(`/companies/${ctx.activeCompany.id}/labour?start=${selected.start_date}&end=${selected.end_date}${facility ? `&facility_id=${facility}` : ""}`)
    : null;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Social" }, { label: "Labour" }]}
        title="Labour"
        description="Aggregated workforce data only. No individual employee records are stored."
        actions={options.length > 0 && <ProjectPicker projects={options} selected={selected?.id} />}
      />
      {data && selected ? <LabourView data={data} companyId={ctx.activeCompany.id} facilities={facilities} facility={facility} canWrite={canWrite(ctx)} /> :
        <p className="text-sm text-muted-foreground">Create a project to choose the reporting period.</p>}
    </>
  );
}
