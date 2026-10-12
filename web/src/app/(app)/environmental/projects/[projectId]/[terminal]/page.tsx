import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { canWrite } from "@/lib/permissions";
import type { TerminalPageData } from "./types";
import { CategoryWorkspace } from "./category-workspace";

export default async function CategoryPage(props: PageProps<"/environmental/projects/[projectId]/[terminal]">) {
  const { projectId, terminal } = await props.params;
  const sp = await props.searchParams;
  const ctx = await requireCompany();
  const data = await engineGet<TerminalPageData>(`/projects/${projectId}/terminals/${terminal}`);
  const supabase = await createClient();
  const [tasks, notes, members] = await Promise.all([
    supabase.from("tasks").select("id, title, description, status, due_date, kind, assignee_id, profiles!tasks_assignee_id_fkey(full_name)")
      .eq("project_id", projectId).eq("terminal_key", terminal).order("created_at", { ascending: false }),
    supabase.from("notes").select("id, body, created_at, terminal_key, profiles(full_name)")
      .eq("project_id", projectId).eq("terminal_key", terminal).order("created_at", { ascending: false }),
    supabase.from("memberships").select("user_id, profiles(full_name, email)").eq("company_id", data.project.company_id).eq("status", "active"),
  ]);
  const t = data.terminal;
  const locked = ["APPROVED", "LOCKED"].includes(data.project.stage);
  return (
    <>
      <PageHeader
        crumbs={[
          { label: "Environmental" },
          { label: "Projects", href: "/environmental/projects" },
          { label: data.project.name, href: `/environmental/projects/${projectId}` },
          { label: t.name },
        ]}
        title={`${t.category_no ? `${t.category_no} ` : ""}${t.name}`}
        description={<>{t.description}{t.excludes && <span className="block">{t.excludes}</span>}</>}
      />
      <CategoryWorkspace
        data={data}
        tasks={(tasks.data ?? []) as never}
        notes={(notes.data ?? []) as never}
        members={(members.data ?? []) as never}
        canWrite={canWrite(ctx) && !locked}
        isInternal={ctx.isInternal}
        initialTab={typeof sp.tab === "string" ? sp.tab : "upload"}
      />
    </>
  );
}
