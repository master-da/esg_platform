"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";
import { fmtDate, fmtNum } from "@/lib/format";
import type { ProjectListItem } from "@/lib/types";

const CALC_LABEL: Record<string, { label: string; tone: "green" | "amber" | "red" | "gray" }> = {
  CALCULATED: { label: "✓ Calculated", tone: "green" },
  PRELIMINARY: { label: "Preliminary", tone: "amber" },
  READY_TO_CATEGORIZE: { label: "Ready to categorize", tone: "gray" },
  NEED_ATTENTION: { label: "● Need attention", tone: "red" },
  NO_DATA: { label: "No data yet", tone: "gray" },
};

export function ProjectsTable({ projects }: { projects: ProjectListItem[] }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("start_desc");
  const rows = useMemo(() => {
    const filtered = projects.filter((p) => p.name.toLowerCase().includes(q.toLowerCase()));
    const by: Record<string, (a: ProjectListItem, b: ProjectListItem) => number> = {
      start_desc: (a, b) => b.start_date.localeCompare(a.start_date),
      start_asc: (a, b) => a.start_date.localeCompare(b.start_date),
      name: (a, b) => a.name.localeCompare(b.name),
      emissions: (a, b) => (b.co2e_t ?? -1) - (a.co2e_t ?? -1),
    };
    return [...filtered].sort(by[sort]);
  }, [projects, q, sort]);

  return (
    <Card>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap gap-2">
          <Input placeholder="Search projects" value={q} onChange={(e) => setQ(e.target.value)} className="w-72" />
          <NativeSelect className="w-48" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
            <option value="start_desc">Date: newest first</option>
            <option value="start_asc">Date: oldest first</option>
            <option value="name">Name</option>
            <option value="emissions">Total emissions</option>
          </NativeSelect>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Project</TableHead>
              <TableHead>Upload deadline</TableHead>
              <TableHead>Stage</TableHead>
              <TableHead>Calculation status</TableHead>
              <TableHead className="text-right">Total tCO₂e</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">No projects yet. Create one for a reporting period.</TableCell></TableRow>
            )}
            {rows.map((p) => {
              const calc = CALC_LABEL[p.calc_status] ?? { label: p.calc_status, tone: "gray" as const };
              return (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/environmental/projects/${p.id}`} className="font-medium hover:underline">{p.name}</Link>
                    <div className="text-xs text-muted-foreground">
                      {fmtDate(p.start_date)} – {fmtDate(p.end_date)}{p.boundary === "division" ? ` · ${p.division_name}` : ""}
                    </div>
                  </TableCell>
                  <TableCell>{p.upload_deadline ? fmtDate(p.upload_deadline) : "No deadline"}</TableCell>
                  <TableCell><StatusBadge status={p.stage} /></TableCell>
                  <TableCell><StatusBadge status={p.calc_status} label={calc.label} tone={calc.tone} /></TableCell>
                  <TableCell className="text-right tabular-nums">{p.co2e_t === null ? "—" : fmtNum(p.co2e_t, 2)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
