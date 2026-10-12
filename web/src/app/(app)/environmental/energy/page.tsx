import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { engineGet } from "@/lib/engine-server";
import { projectsAndSelection } from "@/lib/projects";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { EnergyView, type EnergyData } from "./energy-view";

const KINDS = ["employees", "production_mass", "production_units", "revenue"] as const;

export default async function EnergyPage(props: PageProps<"/environmental/energy">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const { selected, options } = await projectsAndSelection(ctx.activeCompany.id, sp.project);
  const kind = KINDS.find((k) => k === sp.denominator) ?? "production_mass";
  const data = selected ? await engineGet<EnergyData>(`/projects/${selected.id}/energy?denominator=${kind}`) : null;
  const facilities = (await (await createClient()).from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).order("is_company_level").order("name")).data ?? [];
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Energy" }]}
        title="Energy"
        description="Electricity, purchased heat, fuels and on-site renewable generation, with intensity."
        actions={options.length > 0 && <ProjectPicker projects={options} selected={selected?.id} />}
      />
      {selected && data ? (
        <EnergyView data={data} kind={kind} projectId={selected.id} companyId={ctx.activeCompany.id}
          facilities={facilities} canWrite={canWrite(ctx)} />
      ) : <p className="text-sm text-muted-foreground">Create a project and upload electricity or fuel data to see energy figures.</p>}
    </>
  );
}
