import "server-only";
import { engineGet } from "@/lib/engine-server";
import type { ProjectListItem } from "@/lib/types";

/** The company's projects, and the one selected via ?project= (default: most recent). */
export async function projectsAndSelection(companyId: string, wanted: string | string[] | undefined) {
  const projects = await engineGet<ProjectListItem[]>(`/companies/${companyId}/projects`);
  const selected = projects.find((p) => p.id === wanted) ?? projects[0] ?? null;
  return { projects, selected, options: projects.map((p) => ({ id: p.id, name: p.name, stage: p.stage })) };
}
