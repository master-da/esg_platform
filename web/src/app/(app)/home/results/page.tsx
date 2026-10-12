import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import type { ProjectListItem } from "@/lib/types";
import { ProjectPicker } from "./project-picker";
import { ResultsView, type ResultCategory } from "./results-view";

export default async function ResultsPage(props: PageProps<"/home/results">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const projects = await engineGet<ProjectListItem[]>(`/companies/${ctx.activeCompany.id}/projects`);
  const selected = projects.find((p) => p.id === sp.project) ?? projects[0];
  const results = selected ? await engineGet<ResultCategory[]>(`/projects/${selected.id}/results`) : [];
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Home" }, { label: "Results" }]}
        title="Results"
        description="GHG results by category. Click a row to see how it was calculated."
        actions={projects.length > 0 && <ProjectPicker projects={projects.map((p) => ({ id: p.id, name: p.name, stage: p.stage }))} selected={selected?.id} />}
      />
      {selected ? <ResultsView categories={results} /> : <p className="text-sm text-muted-foreground">No projects yet.</p>}
    </>
  );
}
