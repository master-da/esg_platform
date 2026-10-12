"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";

type Framework = { key: string; name: string; version: string | null; description: string | null; source_url: string | null };
type Mapping = { framework_key: string; metric_key: string; disclosure_ref: string; disclosure_title: string | null };
type Metric = { key: string; name: string; unit: string | null; module: string; description: string };

export function FrameworkList({ companyId, frameworks, mappings, metrics, selected, canEdit }: {
  companyId: string; frameworks: Framework[]; mappings: Mapping[]; metrics: Metric[]; selected: string[]; canEdit: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState<string | null>(null);
  const metric = new Map(metrics.map((m) => [m.key, m]));
  async function toggle(key: string, on: boolean) {
    const supabase = createClient();
    const { error } = on
      ? await supabase.from("company_frameworks").insert({ company_id: companyId, framework_key: key })
      : await supabase.from("company_frameworks").delete().eq("company_id", companyId).eq("framework_key", key);
    if (error) return toast.error(error.message);
    router.refresh();
  }
  return (
    <div className="grid gap-4">
      {frameworks.map((f) => {
        const rows = mappings.filter((m) => m.framework_key === f.key);
        return (
          <Card key={f.key}>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>{f.name}</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">{f.description} {f.version && <span className="text-xs">({f.version})</span>}</p>
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={selected.includes(f.key)} disabled={!canEdit} onChange={(e) => toggle(f.key, e.target.checked)} /> We report against this
                </label>
                <Button size="sm" variant="ghost" onClick={() => setOpen(open === f.key ? null : f.key)}>{open === f.key ? "Hide" : `Show ${rows.length} mappings`}</Button>
              </div>
            </CardHeader>
            {open === f.key && (
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>Disclosure</TableHead><TableHead>Metric</TableHead><TableHead>Unit</TableHead><TableHead>Source module</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {rows.map((r) => (
                      <TableRow key={`${r.metric_key}-${r.disclosure_ref}`}>
                        <TableCell>{r.disclosure_ref}{r.disclosure_title && r.disclosure_title !== r.disclosure_ref && <div className="text-xs text-muted-foreground">{r.disclosure_title}</div>}</TableCell>
                        <TableCell>{metric.get(r.metric_key)?.name}<div className="text-xs text-muted-foreground">{metric.get(r.metric_key)?.description}</div></TableCell>
                        <TableCell>{metric.get(r.metric_key)?.unit}</TableCell>
                        <TableCell className="capitalize">{metric.get(r.metric_key)?.module}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}
