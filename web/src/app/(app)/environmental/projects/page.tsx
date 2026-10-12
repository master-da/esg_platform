import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import type { ProjectListItem } from "@/lib/types";
import { NewProjectDialog } from "./new-project-dialog";
import { ProjectsTable } from "./projects-table";

export default async function ProjectsPage() {
  const ctx = await requireCompany();
  const projects = await engineGet<ProjectListItem[]>(`/companies/${ctx.activeCompany.id}/projects`);
  const openTasks = projects.reduce((n, p) => n + p.open_tasks, 0);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Projects" }]}
        title="Projects"
        description="Open a project to upload data, categorize it and review results."
        actions={
          <>
            <span className="rounded-lg border px-3 py-1.5 text-sm">Open tasks ({openTasks})</span>
            {canWrite(ctx) && <NewProjectDialog companyId={ctx.activeCompany.id} />}
          </>
        }
      />
      <ProjectsTable projects={projects} />
      <p className="mt-3 text-xs text-muted-foreground">
        A LOCKED project cannot be edited. Changes need an explicit recalculation that creates a new version.
      </p>
    </>
  );
}
