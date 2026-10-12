"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Download, Upload } from "lucide-react";
import { engine } from "@/lib/engine-client";
import type { FileStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Issue = { row_number: number | null; field: string | null; problem: string; fix: string | null };

/** Wireframe "Upload validation results": every issue names the row and field, with the fix. */
export function ValidationResults({ file, onBack, onUpload, onDownload, canWrite }: {
  file: FileStatus; onBack: () => void; onUpload: () => void; onDownload: () => void; canWrite: boolean;
}) {
  const [issues, setIssues] = useState<Issue[] | null>(null);
  useEffect(() => { engine<Issue[]>(`/files/${file.file_id}/issues`).then(setIssues); }, [file.file_id]);
  return (
    <Card>
      <CardHeader>
        <Button variant="ghost" size="sm" className="w-fit" onClick={onBack}><ArrowLeft /> Back to files</Button>
        <CardTitle>Validation results: {file.original_name}</CardTitle>
        <p className="text-sm text-muted-foreground">Status: Need attention. No rows from this file were added.</p>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Table>
          <TableHeader><TableRow><TableHead className="w-16">Row</TableHead><TableHead>Field</TableHead><TableHead>Problem</TableHead><TableHead>Fix</TableHead></TableRow></TableHeader>
          <TableBody>
            {(issues ?? []).map((i, n) => (
              <TableRow key={n}>
                <TableCell className="tabular-nums">{i.row_number ?? "—"}</TableCell>
                <TableCell>{i.field ?? "—"}</TableCell>
                <TableCell>{i.problem}</TableCell>
                <TableCell className="text-muted-foreground">{i.fix}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm">
          <span className="text-red-800">✕ {issues?.length ?? 0} issue{issues?.length === 1 ? "" : "s"} must be fixed before the file can be categorized.</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={onDownload}><Download /> Download error report</Button>
            {canWrite && <Button size="sm" onClick={onUpload}><Upload /> Upload corrected file</Button>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
