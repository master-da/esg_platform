import Link from "next/link";
import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { engineGet } from "@/lib/engine-server";
import { projectsAndSelection } from "@/lib/projects";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { WasteView, type WasteData } from "./waste-view";

export default async function WastePage(props: PageProps<"/environmental/waste">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const { selected, options } = await projectsAndSelection(ctx.activeCompany.id, sp.project);
  const supabase = await createClient();
  const [data, terminal, facilities] = await Promise.all([
    selected ? engineGet<WasteData>(`/projects/${selected.id}/waste`) : Promise.resolve(null),
    supabase.schema("ref").from("terminals").select("config").eq("key", "s3_c05").single(),
    supabase.from("facilities").select("name").eq("company_id", ctx.activeCompany.id).order("is_company_level").order("name"),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Waste" }]}
        title="Waste"
        description={<>Waste by type, treatment and hazard. Data is shared with Scope 3 category 3.5{selected && <> (<Link className="underline" href={`/environmental/projects/${selected.id}/s3_c05`}>upload a template</Link>)</>}.</>}
        actions={options.length > 0 && <ProjectPicker projects={options} selected={selected?.id} />}
      />
      {selected && data ? (
        <WasteView data={data} projectId={selected.id} columns={(terminal.data?.config as { columns: never }).columns}
          facilities={(facilities.data ?? []).map((f) => f.name)} canWrite={canWrite(ctx) && !["APPROVED", "LOCKED"].includes(selected.stage)} />
      ) : <p className="text-sm text-muted-foreground">Create a project to record waste.</p>}
    </>
  );
}
