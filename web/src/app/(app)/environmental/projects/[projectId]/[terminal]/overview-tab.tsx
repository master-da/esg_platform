"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { fmtDate, fmtNum } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";
import { Grade, Missing } from "@/components/app/values";
import type { RecordRow } from "./types";

/** Wireframe "Data Overview": every record, input vs calculated values, each result opens its trail. */
export function OverviewTab({ projectId, terminalKey, onOpenTrail }: { projectId: string; terminalKey: string; onOpenTrail: (id: number) => void }) {
  const [rows, setRows] = useState<RecordRow[] | null>(null);
  const [mode, setMode] = useState<"input" | "calc">("input");
  const [q, setQ] = useState("");
  const [file, setFile] = useState("");
  const [facility, setFacility] = useState("");
  const [cat, setCat] = useState("");
  useEffect(() => { engine<RecordRow[]>(`/projects/${projectId}/terminals/${terminalKey}/records`).then(setRows).catch((e) => toast.error(e.message)); }, [projectId, terminalKey]);

  const files = useMemo(() => [...new Set((rows ?? []).map((r) => r.file_name).filter(Boolean))] as string[], [rows]);
  const facilities = useMemo(() => [...new Set((rows ?? []).map((r) => r.facility))], [rows]);
  const shown = (rows ?? []).filter((r) => {
    const text = `${r.file_name} ${r.facility} ${r.supplier_name} ${Object.values(r.category_input ?? {}).join(" ")} ${r.categorized_as}`.toLowerCase();
    return (!q || text.includes(q.toLowerCase())) && (!file || r.file_name === file) && (!facility || r.facility === facility) &&
      (!cat || (cat === "uncategorized" ? !r.categorized_as : cat === "accepted" ? !!r.categorized_as : r.calc_status === "UNKNOWN_FACTOR" || r.calc_status === "UNIT_ERROR"));
  });

  if (rows === null) return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} className="w-48" />
        <NativeSelect className="w-44" value={file} onChange={(e) => setFile(e.target.value)} aria-label="File"><option value="">All files</option>{files.map((f) => <option key={f}>{f}</option>)}</NativeSelect>
        <NativeSelect className="w-44" value={facility} onChange={(e) => setFacility(e.target.value)} aria-label="Facility"><option value="">All facilities</option>{facilities.map((f) => <option key={f}>{f}</option>)}</NativeSelect>
        <NativeSelect className="w-48" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Categorization">
          <option value="">Any categorization</option><option value="accepted">Categorized</option><option value="uncategorized">Not yet categorized</option><option value="problems">Calculation issues</option>
        </NativeSelect>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant={mode === "input" ? "default" : "outline"} onClick={() => setMode("input")}>Input values</Button>
          <Button size="sm" variant={mode === "calc" ? "default" : "outline"} onClick={() => setMode("calc")}>Calculated values</Button>
        </div>
      </div>
      <Card>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead><TableHead>Facility</TableHead><TableHead>Period</TableHead><TableHead>Input</TableHead>
                {mode === "input" ? <><TableHead>Original</TableHead><TableHead>Normalized</TableHead></> : <><TableHead>GHG (tCO₂e)</TableHead><TableHead>Grade</TableHead></>}
                <TableHead>Categorized as</TableHead><TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.length === 0 && <TableRow><TableCell colSpan={8} className="py-6 text-center text-muted-foreground">No records.</TableCell></TableRow>}
              {shown.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="text-xs">{r.file_name ?? r.source_type.replace("_", " ")}{r.source_row ? ` · r${r.source_row}` : ""}</TableCell>
                  <TableCell>{r.facility}</TableCell>
                  <TableCell className="whitespace-nowrap text-xs">{fmtDate(r.period_start)} – {fmtDate(r.period_end)}</TableCell>
                  <TableCell className="text-xs">{Object.values(r.category_input ?? {}).join(" · ") || r.supplier_name}</TableCell>
                  {mode === "input" ? (
                    <>
                      <TableCell className="whitespace-nowrap tabular-nums">{fmtNum(r.original_quantity, 4)} {r.original_unit}</TableCell>
                      <TableCell className="whitespace-nowrap tabular-nums">{fmtNum(r.normalized_quantity, 4)} {r.normalized_unit}</TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="tabular-nums">
                        {r.calculation_id && r.calc_status === "CALCULATED" ? (
                          <button className="text-primary underline-offset-2 hover:underline" onClick={() => onOpenTrail(r.calculation_id!)}>{fmtNum(r.co2e_t, 4)}</button>
                        ) : r.calculation_id ? (
                          <button onClick={() => onOpenTrail(r.calculation_id!)}><Missing label={r.calc_status === "UNIT_ERROR" ? "Unit error" : "UNKNOWN"} /></button>
                        ) : <span className="text-xs text-muted-foreground">Not calculated</span>}
                      </TableCell>
                      <TableCell><Grade grade={r.quality_grade} /></TableCell>
                    </>
                  )}
                  <TableCell className="text-xs">{r.categorized_as ? r.categorized_as.split(" > ").slice(1).join(" › ") : <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.file_status ?? r.review_status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">Switch to &quot;Calculated values&quot; to see each result and open its calculation trail. Missing is never shown as 0.</p>
    </div>
  );
}
