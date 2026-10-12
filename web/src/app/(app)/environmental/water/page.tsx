import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { engineGet } from "@/lib/engine-server";
import { projectsAndSelection } from "@/lib/projects";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { WaterView, type WaterData } from "./water-view";

export default async function WaterPage(props: PageProps<"/environmental/water">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const { selected, options } = await projectsAndSelection(ctx.activeCompany.id, sp.project);
  const supabase = await createClient();
  const [data, terminals, facilities, samples, params, thresholds] = await Promise.all([
    selected ? engineGet<WaterData>(`/projects/${selected.id}/water`) : Promise.resolve(null),
    supabase.schema("ref").from("terminals").select("key, name, config").in("key", ["water_withdrawal", "water_discharge"]),
    supabase.from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).order("is_company_level").order("name"),
    supabase.from("wq_samples").select("id, sample_date, parameter_key, value, destination, lab_name, lab_report_ref, result, threshold_snapshot, facilities(name)")
      .eq("company_id", ctx.activeCompany.id).order("sample_date", { ascending: false }).limit(200),
    supabase.schema("ref").from("wq_parameters").select("key, name, unit").order("sort"),
    supabase.schema("ref").from("wq_thresholds").select("*").order("parameter_key").order("version", { ascending: false }),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Water" }]}
        title="Water"
        description="Withdrawal by source, discharge, consumption, and effluent quality against limits stored in the database."
        actions={options.length > 0 && <ProjectPicker projects={options} selected={selected?.id} />}
      />
      <WaterView
        data={data}
        projectId={selected?.id ?? null}
        companyId={ctx.activeCompany.id}
        terminals={(terminals.data ?? []) as never}
        facilities={facilities.data ?? []}
        samples={(samples.data ?? []) as never}
        parameters={params.data ?? []}
        thresholds={(thresholds.data ?? []) as never}
        canWrite={canWrite(ctx) && !!selected && !["APPROVED", "LOCKED"].includes(selected.stage)}
        canWriteSamples={canWrite(ctx)}
        canEditLimits={ctx.canEditLibrary}
      />
    </>
  );
}
