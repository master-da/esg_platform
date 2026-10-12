import Link from "next/link";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { engineGet } from "@/lib/engine-server";
import { fmtDateTime } from "@/lib/format";
import { requireInternal } from "@/lib/session";

type Queue = {
  files: { file_id: string; original_name: string; uploaded_at: string; records: number; project_id: string; terminal_key: string; company: string; project: string; category: string }[];
  factor_requests: { id: string; title: string; description: string; created_at: string; project_id: string; terminal_key: string; company: string; project: string }[];
};

export default async function ReviewQueuePage() {
  await requireInternal();
  const q = await engineGet<Queue>("/internal/review-queue");
  return (
    <>
      <PageHeader crumbs={[{ label: "Internal" }, { label: "Review queue" }]} title="Review queue"
        description="Files with preliminary calculations waiting for an internal reviewer to confirm them as Calculated, and open factor requests." />
      <div className="grid gap-6">
        <Card>
          <CardHeader><CardTitle>Files awaiting confirmation ({q.files.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Company</TableHead><TableHead>Project</TableHead><TableHead>Category</TableHead><TableHead>File</TableHead><TableHead>Rows</TableHead><TableHead>Uploaded</TableHead></TableRow></TableHeader>
              <TableBody>
                {q.files.length === 0 && <TableRow><TableCell colSpan={6} className="py-6 text-center text-muted-foreground">Nothing to review.</TableCell></TableRow>}
                {q.files.map((f) => (
                  <TableRow key={f.file_id}>
                    <TableCell>{f.company}</TableCell><TableCell>{f.project}</TableCell><TableCell>{f.category}</TableCell>
                    <TableCell><Link className="text-primary hover:underline" href={`/environmental/projects/${f.project_id}/${f.terminal_key}`}>{f.original_name}</Link></TableCell>
                    <TableCell className="tabular-nums">{f.records}</TableCell><TableCell className="text-xs">{fmtDateTime(f.uploaded_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-2 text-xs text-muted-foreground">Switch the active company in the top bar if the file belongs to another company, then confirm or return it from the file menu.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Factor requests ({q.factor_requests.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Company</TableHead><TableHead>Request</TableHead><TableHead>Requested</TableHead></TableRow></TableHeader>
              <TableBody>
                {q.factor_requests.length === 0 && <TableRow><TableCell colSpan={3} className="py-6 text-center text-muted-foreground">No open requests.</TableCell></TableRow>}
                {q.factor_requests.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.company}<div className="text-xs text-muted-foreground">{r.project}</div></TableCell>
                    <TableCell>{r.title}<div className="text-xs text-muted-foreground">{r.description}</div></TableCell>
                    <TableCell className="text-xs">{fmtDateTime(r.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-2 text-xs text-muted-foreground">Add the cited factor in the Emission factor library, then recalculate the project to pick it up in a new calculation version.</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
