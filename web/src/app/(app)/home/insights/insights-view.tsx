"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Download } from "lucide-react";
import { fmtNum } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BreakdownBars, Sparkline, StackedColumns } from "@/components/charts/charts";
import { SCOPE_COLORS, SERIES } from "@/components/charts/palette";
import { DrillSheet, type DrillQuery } from "@/components/app/drill-sheet";
import { NativeSelect } from "@/components/app/native-select";
import { Missing } from "@/components/app/values";

type Delta = { pct: number | null; months: number };
type Breakdown = { key: string; label: string; co2e_t: number; records: number };
export type InsightsData = {
  project: { id: string; name: string } | null;
  previous: { name: string } | null;
  projects: { id: string; name: string; stage: string }[];
  total_t: number | null;
  scope_cards: { scope: number; total_t: number | null; delta: Delta; trend: { project: string; total_t: number | null }[] }[];
  yearly: ({ project: string; project_id: string } & Record<string, number | string>)[];
  by_source: Breakdown[]; by_facility: Breakdown[]; by_grade: Breakdown[];
  monthly: ({ month: string } & Record<string, number | string>)[];
  unknown: number;
};
type Filters = { project: string; facility: string; grade: string; path: string };

const SCOPES = ["Scope 1", "Scope 2", "Scope 3"].map((s) => ({ key: s, label: s, color: SCOPE_COLORS[s] }));

export function InsightsView({ data, companyId, facilities, categories, filters }: {
  data: InsightsData; companyId: string; facilities: { id: string; name: string }[];
  categories: { path: string; name: string; ghg_category: string }[]; filters: Filters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [drill, setDrill] = useState<DrillQuery>(null);
  if (!data.project) return <p className="text-sm text-muted-foreground">No organization-wide project yet.</p>;
  const pid = data.project.id;
  const base = { project_id: pid, facility_id: filters.facility || undefined, grade: filters.grade || undefined, path: filters.path || undefined };

  function set(next: Partial<Filters>) {
    const q = new URLSearchParams(Object.entries({ ...filters, project: pid, ...next }).filter(([, v]) => v));
    router.push(`${pathname}?${q}`);
  }
  function exportYearly() {
    const header = ["Project", ...SCOPES.map((s) => `${s.label} (t CO2e)`)];
    const lines = data.yearly.map((y) => [y.project, ...SCOPES.map((s) => (y[s.key] === undefined ? "Missing" : String(y[s.key])))]);
    const csv = [header, ...lines].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "emissions_by_scope_and_year.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const views = [{ path: "", label: "Overview" }, { path: "s1", label: "Scope 1" }, { path: "s2", label: "Scope 2" }, { path: "s3", label: "Scope 3" },
    ...categories.map((c) => ({ path: c.path, label: `${c.ghg_category} ${c.name}` }))];

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect className="w-64" value={filters.path} onChange={(e) => set({ path: e.target.value })} aria-label="View">
          {views.map((v) => <option key={v.path} value={v.path}>{v.label}</option>)}
        </NativeSelect>
        <NativeSelect className="w-52" value={pid} onChange={(e) => set({ project: e.target.value })} aria-label="Year">
          {data.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </NativeSelect>
        <NativeSelect className="w-52" value={filters.facility} onChange={(e) => set({ facility: e.target.value })} aria-label="Facility">
          <option value="">All facilities (company)</option>{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </NativeSelect>
        <NativeSelect className="w-44" value={filters.grade} onChange={(e) => set({ grade: e.target.value })} aria-label="Data quality">
          <option value="">Any data quality</option><option value="A">Grade A (primary)</option><option value="B">Grade B (secondary)</option><option value="C">Grade C (estimated)</option>
        </NativeSelect>
      </div>
      {data.unknown > 0 && (
        <p className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800">
          {data.unknown} rows in {data.project.name} have no emission factor (UNKNOWN). They are excluded from every figure below, never counted as zero.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {data.scope_cards.map((c) => (
          <button key={c.scope} className="rounded-xl border bg-card p-4 text-left transition-colors hover:bg-accent/40"
            onClick={() => setDrill({ title: `Scope ${c.scope} · ${data.project!.name}`, params: { ...base, scope: c.scope } })}>
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><span className="inline-block size-2.5 rounded-sm" style={{ background: SCOPE_COLORS[`Scope ${c.scope}`] }} />Scope {c.scope}</div>
            <div className="mt-1 text-2xl font-semibold">{c.total_t === null ? <Missing label="No calculated data" /> : <>{fmtNum(c.total_t, 1)}<span className="ml-1 text-base font-normal text-muted-foreground">t CO₂e</span></>}</div>
            <div className="mt-1 text-xs">
              {c.delta.pct === null ? <span className="text-muted-foreground">No comparison{data.previous ? "" : " (no earlier project)"}</span> :
                <span className={c.delta.pct > 0 ? "text-red-700" : "text-emerald-800"}>{c.delta.pct > 0 ? "▲" : "▼"} {Math.abs(c.delta.pct).toFixed(1)}% <span className="text-muted-foreground">vs same {c.delta.months} months of {data.previous?.name}</span></span>}
            </div>
            <Sparkline data={c.trend.map((t) => ({ label: t.project, value: t.total_t }))} color={SCOPE_COLORS[`Scope ${c.scope}`]} />
          </button>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Emissions by scope and year (t CO₂e)</CardTitle>
          <Button size="sm" variant="outline" onClick={exportYearly}><Download /> Export</Button>
        </CardHeader>
        <CardContent>
          <StackedColumns data={data.yearly as never} x="project" series={SCOPES} unit="t CO₂e"
            onSelect={(row, key) => setDrill({ title: `${key} · ${row.project}`, params: { ...base, project_id: String(row.project_id), scope: Number(key.slice(-1)) } })} />
          <Table className="mt-3">
            <TableHeader><TableRow><TableHead>Project</TableHead>{SCOPES.map((s) => <TableHead key={s.key} className="text-right">{s.label}</TableHead>)}</TableRow></TableHeader>
            <TableBody>{data.yearly.map((y) => (
              <TableRow key={y.project_id}><TableCell>{y.project}</TableCell>{SCOPES.map((s) => (
                <TableCell key={s.key} className="text-right tabular-nums">{y[s.key] === undefined ? <span className="text-muted-foreground">—</span> : fmtNum(y[s.key] as number, 2)}</TableCell>))}</TableRow>))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>By source (t CO₂e)</CardTitle></CardHeader>
          <CardContent>
            <BreakdownBars data={data.by_source.map((b) => ({ key: b.key, label: b.label.split(" > ").slice(-2).join(" › "), value: Number(b.co2e_t) }))} color={SERIES[0]} unit="t CO₂e"
              onSelect={(b) => setDrill({ title: b.label, params: { ...base, path: b.key } })} />
            <p className="mt-1 text-xs text-muted-foreground">Grouped by the emission-factor taxonomy, so each slice matches a calculation category.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>By facility (t CO₂e)</CardTitle></CardHeader>
          <CardContent>
            <BreakdownBars data={data.by_facility.map((b) => ({ key: b.key, label: b.label, value: Number(b.co2e_t) }))} color={SERIES[0]} unit="t CO₂e"
              onSelect={(b) => setDrill({ title: b.label, params: { ...base, facility_id: b.key } })} />
            <p className="mt-1 text-xs text-muted-foreground">Company total = sum of facilities ({fmtNum(data.total_t, 2)} t CO₂e).</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Monthly trend by scope (t CO₂e)</CardTitle></CardHeader>
          <CardContent>
            <StackedColumns data={data.monthly as never} x="month" series={SCOPES} unit="t CO₂e"
              onSelect={(row, key) => setDrill({ title: `${key} · ${row.month}`, params: { ...base, scope: Number(key.slice(-1)), month: String(row.month) } })} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>By data quality</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableBody>
                {data.by_grade.map((g) => (
                  <TableRow key={g.key} className={cn("cursor-pointer")} onClick={() => setDrill({ title: `${g.label} data`, params: { ...base, grade: g.key } })}>
                    <TableCell>{g.label}<div className="text-xs text-muted-foreground">{g.key === "A" ? "Primary, measured" : g.key === "B" ? "Reliable secondary" : "Estimated or default (incl. spend-based)"}</div></TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(g.co2e_t, 2)} t CO₂e</TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">{data.total_t ? fmtNum((g.co2e_t / data.total_t) * 100, 1) : "—"}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
      <DrillSheet companyId={companyId} query={drill} onClose={() => setDrill(null)} />
    </div>
  );
}
