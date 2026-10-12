"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Download, FileUp, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";
import { engine, engineDownload } from "@/lib/engine-client";
import { fmtDate } from "@/lib/format";
import type { FileStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/app/status-badge";
import { BillUpload } from "./bill-upload";
import type { TerminalPageData } from "./types";
import { ValidationResults } from "./validation-results";

export function UploadTab({ data, canWrite, isInternal, onReviewCategorizations }: {
  data: TerminalPageData; canWrite: boolean; isInternal: boolean; onReviewCategorizations: () => void;
}) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [issuesFor, setIssuesFor] = useState<FileStatus | null>(null);
  const { project, terminal: t, files } = data;
  const failing = files.filter((f) => f.status === "NEED_ATTENTION");

  async function upload(file: File) {
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await engine<{ validation_passed: boolean; rows: number; issues: number; records_created: number }>(
        `/projects/${project.id}/terminals/${t.key}/uploads`, { method: "POST", body: form });
      if (r.validation_passed) toast.success(`${file.name}: ${r.records_created} rows added, ready to categorize`);
      else toast.error(`${file.name}: ${r.issues} issue${r.issues === 1 ? "" : "s"} found. Fix them and upload again.`);
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message, { duration: 10000 });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function action(f: FileStatus, kind: "original" | "calculated" | "delete" | "confirm" | "reject" | "errors") {
    try {
      if (kind === "original") {
        const { url } = await engine<{ url: string }>(`/files/${f.file_id}/original`);
        window.open(url, "_blank");
      } else if (kind === "calculated") {
        await engineDownload(`/files/${f.file_id}/calculated`, `calculated_${f.original_name}`);
      } else if (kind === "errors") {
        await engineDownload(`/files/${f.file_id}/issues.xlsx`, `errors_${f.original_name}`);
      } else if (kind === "delete") {
        if (!window.confirm(`Delete ${f.original_name}? Its rows leave the active dataset; the audit log keeps the history.`)) return;
        await engine(`/files/${f.file_id}`, { method: "DELETE" });
        toast.success("File deleted");
      } else {
        const comment = kind === "reject" ? window.prompt("What does the client need to fix?") : null;
        if (kind === "reject" && !comment) return;
        await engine(`/files/${f.file_id}/review`, { method: "POST", json: { action: kind, comment } });
        toast.success(kind === "confirm" ? "Confirmed as Calculated" : "Returned to the client");
      }
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (issuesFor) {
    return <ValidationResults file={issuesFor} onBack={() => setIssuesFor(null)} onUpload={() => { setIssuesFor(null); input.current?.click(); }}
      onDownload={() => action(issuesFor, "errors")} canWrite={canWrite} />;
  }

  return (
    <div className="grid gap-4">
      {canWrite && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
          className={cn("rounded-xl border-2 border-dashed p-6 text-center transition-colors", dragging ? "border-primary bg-accent" : "border-emerald-300 bg-emerald-50/40")}
        >
          <div className="flex flex-wrap items-center justify-center gap-2 text-sm">
            <FileUp className="size-4" /> Drop a file here, or
            <Button size="sm" onClick={() => input.current?.click()} disabled={busy}>{busy ? "Uploading…" : "Upload file"}</Button>
            <Button size="sm" variant="outline" onClick={() => engineDownload(`/projects/${project.id}/terminals/${t.key}/template`, `${t.key}_template.xlsx`)}>
              <Download /> Download template
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">.xlsx or .csv · this category&apos;s template only (v{t.template_version}). A file from another category is rejected with a message naming the right place.</p>
          <input ref={input} type="file" accept=".xlsx,.csv" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </div>
      )}
      {canWrite && t.accepts_bills && <BillUpload projectId={project.id} terminal={t} />}

      <Card>
        <CardHeader><CardTitle>Uploaded files</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow><TableHead>File</TableHead><TableHead>Uploaded</TableHead><TableHead>Rows</TableHead><TableHead>Status</TableHead><TableHead className="w-10" /></TableRow>
            </TableHeader>
            <TableBody>
              {files.length === 0 && <TableRow><TableCell colSpan={5} className="py-6 text-center text-muted-foreground">No files uploaded for this category yet.</TableCell></TableRow>}
              {files.map((f) => (
                <TableRow key={f.file_id}>
                  <TableCell>
                    <div className="font-medium">{f.original_name}</div>
                    {f.kind === "bill" && <div className="text-xs text-muted-foreground">Bill / invoice</div>}
                    {f.last_review_action === "reject" && f.status === "NEED_ATTENTION" && <div className="text-xs text-red-700">Returned: {f.last_review_comment}</div>}
                  </TableCell>
                  <TableCell className="text-sm">{fmtDate(f.uploaded_at)}{f.uploaded_by_name ? <div className="text-xs text-muted-foreground">{f.uploaded_by_name}</div> : null}</TableCell>
                  <TableCell className="tabular-nums">{f.row_count}</TableCell>
                  <TableCell>
                    <StatusBadge status={f.status} label={f.status === "CALCULATED" ? "✓ Calculated" : f.status === "AWAITING_CONFIRMATION" ? "Awaiting confirmation" : undefined} />
                    {!f.validation_passed && <button className="ml-2 text-xs text-red-700 hover:underline" onClick={() => setIssuesFor(f)}>View issues</button>}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger render={<Button size="icon-sm" variant="ghost" aria-label="File actions" />}>
                        <MoreHorizontal />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => action(f, "original")}>Download original file</DropdownMenuItem>
                        {isInternal && <DropdownMenuItem onClick={() => action(f, "calculated")}>Download calculated file (internal)</DropdownMenuItem>}
                        {!f.validation_passed && <DropdownMenuItem onClick={() => setIssuesFor(f)}>View validation issues</DropdownMenuItem>}
                        {isInternal && f.status === "PRELIMINARY" && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => action(f, "confirm")}>Confirm as Calculated</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => action(f, "reject")}>Return to client</DropdownMenuItem>
                          </>
                        )}
                        {canWrite && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem variant="destructive" onClick={() => action(f, "delete")}>Delete file</DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {(failing.length > 0 || data.needs_categorization > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm">
          <span className="text-red-800">
            {failing.length > 0 ? `✕ Resolve the issues in ${failing.length} file${failing.length > 1 ? "s" : ""} to categorize all data.` : `${data.needs_categorization} input${data.needs_categorization > 1 ? "s" : ""} waiting for categorization.`}
          </span>
          <div className="flex gap-2">
            {failing.some((f) => !f.validation_passed) && (
              <Button size="sm" variant="outline" onClick={() => setIssuesFor(failing.find((f) => !f.validation_passed)!)}>Fix validation errors</Button>
            )}
            <Button size="sm" onClick={onReviewCategorizations}>Review categorizations</Button>
          </div>
        </div>
      )}
    </div>
  );
}
