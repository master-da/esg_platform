import { PageHeader } from "@/components/app/page-header";
import { StatusBadge } from "@/components/app/status-badge";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { canApprove, canWrite } from "@/lib/permissions";
import { fmtDate, fmtNum } from "@/lib/format";
import type { Coverage, FileStatus, ProjectDetail } from "@/lib/types";
import { ProgressBar } from "./progress-bar";
import { ProjectActions } from "./project-actions";
import { ProjectTabs } from "./project-tabs";

export default async function ProjectPage(props: PageProps<"/environmental/projects/[projectId]">) {
  const { projectId } = await props.params;
  const ctx = await requireCompany();
  const [detail, coverage] = await Promise.all([
    engineGet<ProjectDetail>(`/projects/${projectId}`),
    engineGet<Coverage[]>(`/projects/${projectId}/coverage`),
  ]);
  const supabase = await createClient();
  const [files, notes, issues, members] = await Promise.all([
    supabase.from("v_file_status").select("*").eq("project_id", projectId).order("uploaded_at", { ascending: false }),
    supabase.from("notes").select("id, body, created_at, terminal_key, profiles(full_name)").eq("project_id", projectId).order("created_at", { ascending: false }),
    supabase.from("validation_issues").select("file_id, row_number, field, problem").in(
      "file_id", (await supabase.from("v_file_status").select("file_id").eq("project_id", projectId)).data?.map((f) => f.file_id) ?? []),
    supabase.from("memberships").select("user_id, profiles(full_name, email)").eq("company_id", detail.project.company_id).eq("status", "active"),
  ]);
  const p = detail.project;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Projects", href: "/environmental/projects" }, { label: p.name }]}
        title={p.name}
        description={<span className="flex items-center gap-2">Project · <StatusBadge status={p.stage} /></span>}
        actions={<ProjectActions project={p} canWrite={canWrite(ctx)} canApprove={canApprove(ctx)} />}
      />
      <div className="mb-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-4">
        <div><div className="text-xs text-muted-foreground">Time period</div><div className="font-medium">{fmtDate(p.start_date)} – {fmtDate(p.end_date)}</div></div>
        <div><div className="text-xs text-muted-foreground">Upload deadline</div><div className="font-medium">{p.upload_deadline ? fmtDate(p.upload_deadline) : "No deadline"}</div></div>
        <div><div className="text-xs text-muted-foreground">Open tasks</div><div className="font-medium">{detail.open_tasks}</div></div>
        <div className="sm:text-right"><div className="text-xs text-muted-foreground">Total emissions (tCO₂e)</div><div className="text-xl font-semibold tabular-nums">{detail.co2e_t === null ? "—" : fmtNum(detail.co2e_t, 2)}</div></div>
      </div>
      <ProgressBar progress={detail.progress} />
      <ProjectTabs
        detail={detail}
        files={(files.data ?? []) as FileStatus[]}
        notes={(notes.data ?? []) as never}
        issues={(issues.data ?? []) as never}
        members={(members.data ?? []) as never}
        coverage={coverage}
        canWrite={canWrite(ctx) && !["APPROVED", "LOCKED"].includes(p.stage)}
      />
    </>
  );
}
