"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { createClient } from "@/lib/supabase/client";
import { fmtDate, fmtDateTime, fmtNum } from "@/lib/format";
import type { CategoryRow, Coverage, FileStatus, ProjectDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

type Note = { id: string; body: string; created_at: string; terminal_key: string | null; profiles: { full_name: string | null } | null };
type IssueRow = { file_id: string; row_number: number | null; field: string | null; problem: string };
type Member = { user_id: string; profiles: { full_name: string | null; email: string } | null };

const CAT_STATUS: Record<string, { label: string; tone: "green" | "amber" | "red" | "gray" | "blue" }> = {
  CALCULATED: { label: "Calculated", tone: "green" },
  PRELIMINARY: { label: "Preliminary", tone: "amber" },
  READY_TO_CATEGORIZE: { label: "Ready to categorize", tone: "gray" },
  NEED_ATTENTION: { label: "Need attention", tone: "red" },
  NO_DATA: { label: "No data", tone: "gray" },
  NOT_APPLICABLE: { label: "Not applicable", tone: "blue" },
};

export function ProjectTabs({ detail, files, notes, issues, members, coverage, canWrite }: {
  detail: ProjectDetail; files: FileStatus[]; notes: Note[]; issues: IssueRow[]; members: Member[]; coverage: Coverage[]; canWrite: boolean;
}) {
  const pid = detail.project.id;
  const terminalName = new Map(detail.categories.map((c) => [c.terminal_key, c.name]));
  const scopes = [1, 2, 3].map((s) => ({ scope: s, rows: detail.categories.filter((c) => c.module === "ghg" && c.scope === s) }));
  const other = detail.categories.filter((c) => c.module !== "ghg");
  const gaps = coverage.filter((c) => c.missing_months.length > 0);
  const qualityCount = files.filter((f) => f.status === "NEED_ATTENTION").length + gaps.length +
    detail.categories.filter((c) => c.in_scope && c.status === "NO_DATA" && c.module === "ghg").length;

  return (
    <Tabs defaultValue="categories">
      <TabsList>
        <TabsTrigger value="categories">Categories</TabsTrigger>
        <TabsTrigger value="uploads">All uploads ({files.length})</TabsTrigger>
        <TabsTrigger value="quality">Quality checks{qualityCount ? <span className="ml-1 size-1.5 rounded-full bg-red-600" /> : null}</TabsTrigger>
        <TabsTrigger value="notes">Notes</TabsTrigger>
        <TabsTrigger value="versions">Versions</TabsTrigger>
      </TabsList>

      <TabsContent value="categories" className="grid gap-4">
        {scopes.map(({ scope, rows }) => rows.length > 0 && (
          <CategoryTable key={scope} title={`Scope ${scope}`} rows={rows} pid={pid} members={members} canWrite={canWrite} />
        ))}
        {other.length > 0 && <CategoryTable title="Energy, water & waste data" rows={other} pid={pid} members={members} canWrite={canWrite} />}
      </TabsContent>

      <TabsContent value="uploads">
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow><TableHead>File</TableHead><TableHead>Category</TableHead><TableHead>Uploaded</TableHead><TableHead>Rows</TableHead><TableHead>Status</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {files.length === 0 && <TableRow><TableCell colSpan={5} className="py-6 text-center text-muted-foreground">No uploads yet.</TableCell></TableRow>}
                {files.map((f) => (
                  <TableRow key={f.file_id}>
                    <TableCell><Link className="hover:underline" href={`/environmental/projects/${pid}/${f.terminal_key}`}>{f.original_name}</Link></TableCell>
                    <TableCell>{terminalName.get(f.terminal_key)}</TableCell>
                    <TableCell>{fmtDateTime(f.uploaded_at)}</TableCell>
                    <TableCell className="tabular-nums">{f.row_count}</TableCell>
                    <TableCell><StatusBadge status={f.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="quality" className="grid gap-4">
        <QualityChecks detail={detail} files={files} issues={issues} pid={pid} gaps={gaps} />
      </TabsContent>

      <TabsContent value="notes">
        <NotesPanel pid={pid} companyId={detail.project.company_id} notes={notes.filter((n) => !n.terminal_key)} canWrite={canWrite} />
      </TabsContent>

      <TabsContent value="versions">
        <Card>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Version</TableHead><TableHead>Reason</TableHead><TableHead>Library as of</TableHead><TableHead>Created</TableHead><TableHead>State</TableHead></TableRow></TableHeader>
              <TableBody>
                {detail.versions.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell className="font-medium">v{v.version_no}{v.id === detail.project.current_version_id ? " (current)" : ""}</TableCell>
                    <TableCell>{v.reason}</TableCell>
                    <TableCell>{fmtDateTime(v.library_as_of)}</TableCell>
                    <TableCell>{fmtDateTime(v.created_at)}{v.created_by_name ? ` · ${v.created_by_name}` : ""}</TableCell>
                    <TableCell>{v.frozen_at ? <StatusBadge status="LOCKED" label="Frozen" /> : "Open"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}

function CategoryTable({ title, rows, pid, members, canWrite }: { title: string; rows: CategoryRow[]; pid: string; members: Member[]; canWrite: boolean }) {
  const router = useRouter();
  async function patch(key: string, body: Record<string, unknown>) {
    try {
      await engine(`/projects/${pid}/categories/${key}`, { method: "PATCH", json: body });
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  async function toggleScope(c: CategoryRow) {
    if (c.in_scope) {
      const reason = window.prompt(`Why is "${c.name}" not applicable for this project? (shown in reports)`);
      if (!reason) return;
      await patch(c.terminal_key, { in_scope: false, na_reason: reason });
    } else {
      await patch(c.terminal_key, { in_scope: true });
    }
  }
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Category</TableHead>
              <TableHead>Assigned to</TableHead>
              <TableHead>Tasks</TableHead>
              <TableHead>Data</TableHead>
              <TableHead className="w-56">Calculation</TableHead>
              <TableHead className="text-right">tCO₂e</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => {
              const st = CAT_STATUS[c.status];
              const pct = c.records ? (c.calculated / c.records) * 100 : 0;
              return (
                <TableRow key={c.terminal_key} className={!c.in_scope ? "opacity-60" : undefined}>
                  <TableCell>
                    <Link href={`/environmental/projects/${pid}/${c.terminal_key}`} className="font-medium hover:underline">
                      {c.category_no ? `${c.category_no} ` : ""}{c.name}
                    </Link>
                    {!c.enabled && <div className="text-xs text-amber-700">{c.disabled_reason}</div>}
                    {!c.in_scope && <div className="text-xs text-muted-foreground">Not applicable: {c.na_reason}</div>}
                    {canWrite && c.enabled && (
                      <button className="block text-xs text-muted-foreground hover:underline" onClick={() => toggleScope(c)}>
                        {c.in_scope ? "Mark not applicable" : "Mark applicable"}
                      </button>
                    )}
                  </TableCell>
                  <TableCell>
                    {canWrite ? (
                      <NativeSelect className="w-40" value={c.assignee_id ?? ""} onChange={(e) => patch(c.terminal_key, { assignee_id: e.target.value || null })}>
                        <option value="">Unassigned</option>
                        {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.profiles?.full_name ?? m.profiles?.email}</option>)}
                      </NativeSelect>
                    ) : (c.assignee_name ?? "—")}
                  </TableCell>
                  <TableCell className="tabular-nums">{c.open_tasks || ""}</TableCell>
                  <TableCell className="text-sm">{c.files ? `${c.files} file${c.files > 1 ? "s" : ""}` : <span className="text-muted-foreground">No data</span>}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                        <div className={c.status === "NEED_ATTENTION" ? "h-full bg-red-600" : "h-full bg-emerald-700"} style={{ width: `${pct}%` }} />
                      </div>
                      <StatusBadge status={c.status} label={st?.label} tone={st?.tone} />
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{c.co2e_t === null ? "—" : fmtNum(c.co2e_t, 2)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function QualityChecks({ detail, files, issues, pid, gaps }: { detail: ProjectDetail; files: FileStatus[]; issues: IssueRow[]; pid: string; gaps: Coverage[] }) {
  const attention = files.filter((f) => f.status === "NEED_ATTENTION");
  const missing = detail.categories.filter((c) => c.in_scope && c.status === "NO_DATA" && c.enabled && c.module === "ghg");
  const na = detail.categories.filter((c) => !c.in_scope);
  const issuesByFile = new Map<string, IssueRow[]>();
  for (const i of issues) issuesByFile.set(i.file_id, [...(issuesByFile.get(i.file_id) ?? []), i]);
  return (
    <>
      <Card>
        <CardHeader><CardTitle>Files that need attention ({attention.length})</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm">
          {attention.length === 0 && <p className="text-muted-foreground">None.</p>}
          {attention.map((f) => (
            <div key={f.file_id} className="rounded-md border p-2">
              <Link className="font-medium hover:underline" href={`/environmental/projects/${pid}/${f.terminal_key}`}>{f.original_name}</Link>
              <span className="text-muted-foreground"> · {detail.categories.find((c) => c.terminal_key === f.terminal_key)?.name}</span>
              <div className="text-xs text-muted-foreground">
                {!f.validation_passed ? `${issuesByFile.get(f.file_id)?.length ?? 0} validation issues` :
                  f.calc_errors ? `${f.calc_errors} rows without an emission factor or with an unsupported unit` :
                  f.last_review_action === "reject" ? `Returned by reviewer: ${f.last_review_comment}` : ""}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Missing months ({gaps.length})</CardTitle></CardHeader>
        <CardContent className="text-sm">
          {gaps.length === 0 ? <p className="text-muted-foreground">Every facility that reports in a category covers every month of the project.</p> : (
            <Table>
              <TableHeader><TableRow><TableHead>Category</TableHead><TableHead>Facility</TableHead><TableHead>Coverage</TableHead><TableHead>Missing</TableHead></TableRow></TableHeader>
              <TableBody>
                {gaps.map((g) => (
                  <TableRow key={`${g.terminal_key}-${g.facility_id}`}>
                    <TableCell><Link className="hover:underline" href={`/environmental/projects/${pid}/${g.terminal_key}`}>{g.terminal_name}</Link></TableCell>
                    <TableCell>{g.facility}</TableCell>
                    <TableCell className="tabular-nums">{g.covered_months}/{g.expected_months} months</TableCell>
                    <TableCell className="flex flex-wrap gap-1">{g.missing_months.map((m) => <StatusBadge key={m} status="MISSING" label={m} tone="red" />)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>In-scope categories with no data ({missing.length})</CardTitle></CardHeader>
        <CardContent className="text-sm">
          {missing.length === 0 ? <p className="text-muted-foreground">Every in-scope category has data.</p> : (
            <ul className="grid gap-1 sm:grid-cols-2">
              {missing.map((c) => <li key={c.terminal_key}><StatusBadge status="MISSING" label="Missing" tone="red" /> {c.category_no} {c.name}</li>)}
            </ul>
          )}
          <p className="mt-3 text-xs text-muted-foreground">Missing data is reported as Missing, never as zero. Mark a category not applicable (with a reason) if it does not apply.</p>
        </CardContent>
      </Card>
      {na.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Not applicable ({na.length})</CardTitle></CardHeader>
          <CardContent className="text-sm"><ul className="space-y-1">{na.map((c) => <li key={c.terminal_key}>{c.category_no} {c.name}: <span className="text-muted-foreground">{c.na_reason}</span></li>)}</ul></CardContent>
        </Card>
      )}
    </>
  );
}

export function NotesPanel({ pid, companyId, terminalKey = null, notes, canWrite }: {
  pid: string; companyId: string; terminalKey?: string | null; notes: Note[]; canWrite: boolean;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  async function add() {
    if (!body.trim()) return;
    const { error } = await createClient().from("notes").insert({ company_id: companyId, project_id: pid, terminal_key: terminalKey, body });
    if (error) return toast.error(error.message);
    setBody("");
    router.refresh();
  }
  return (
    <div className="grid gap-3">
      {canWrite && (
        <div className="grid gap-2">
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a note" rows={3} />
          <div><Button size="sm" onClick={add}>Add note</Button></div>
        </div>
      )}
      {notes.length === 0 && <p className="text-sm text-muted-foreground">No notes yet.</p>}
      {notes.map((n) => (
        <div key={n.id} className="rounded-md border p-2 text-sm">
          <div className="whitespace-pre-wrap">{n.body}</div>
          <div className="mt-1 text-xs text-muted-foreground">{n.profiles?.full_name ?? "—"} · {fmtDate(n.created_at)}</div>
        </div>
      ))}
    </div>
  );
}
