"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AlertTriangle, Download, Info } from "lucide-react";
import { toast } from "sonner";
import { engine, engineDownloadPost } from "@/lib/engine-client";
import { fmtDate, fmtDateTime } from "@/lib/format";
import type { ProjectListItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

export type ReportRow = { id: string; export_type: string; format: string; period_start: string; period_end: string; file_name: string; project_name: string | null; generated_by_name: string | null; generated_at: string; warnings: { level: string; text: string }[] };
type Warning = { level: "error" | "warning" | "info"; text: string };

const SECTIONS = [
  ["emissions_by_ghg_category", "Emissions by GHG category"],
  ["emissions_by_internal_category", "Emissions by internal category"],
  ["energy_water_waste", "Energy, water and waste"],
  ["calculation_trail", "Calculation trail"],
  ["assumptions_quality", "Assumptions and data-quality notes"],
] as const;

const iso = (d: Date) => d.toISOString().slice(0, 10);

function quickPicks(fiscalStart: string) {
  const today = new Date();
  const y = today.getUTCFullYear(), m = today.getUTCMonth();
  const [fm, fd] = fiscalStart.split("-").map(Number);
  let fyStart = new Date(Date.UTC(y, fm - 1, fd));
  if (fyStart > today) fyStart = new Date(Date.UTC(y - 1, fm - 1, fd));
  const lastFyStart = new Date(Date.UTC(fyStart.getUTCFullYear() - 1, fm - 1, fd));
  const lastFyEnd = new Date(fyStart.getTime() - 86400000);
  const q = Math.floor(m / 3);
  const lastQStart = new Date(Date.UTC(q === 0 ? y - 1 : y, q === 0 ? 9 : (q - 1) * 3, 1));
  const lastQEnd = new Date(Date.UTC(lastQStart.getUTCFullYear(), lastQStart.getUTCMonth() + 3, 0));
  return [
    { label: "Last financial year", start: iso(lastFyStart), end: iso(lastFyEnd) },
    { label: "Last calendar year", start: `${y - 1}-01-01`, end: `${y - 1}-12-31` },
    { label: "Last quarter", start: iso(lastQStart), end: iso(lastQEnd) },
    { label: "Last month", start: iso(new Date(Date.UTC(y, m - 1, 1))), end: iso(new Date(Date.UTC(y, m, 0))) },
  ];
}

export function ExportWizard({ projects, frameworks, fiscal, history }: {
  projects: ProjectListItem[]; frameworks: { key: string; name: string; description: string | null }[];
  fiscal: { fiscal_year_start: string; fiscal_year_end: string }; history: ReportRow[];
}) {
  const router = useRouter();
  const [type, setType] = useState("custom");
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const project = projects.find((p) => p.id === projectId);
  const [start, setStart] = useState(project?.start_date ?? "");
  const [end, setEnd] = useState(project?.end_date ?? "");
  const [sections, setSections] = useState<string[]>(["emissions_by_ghg_category", "energy_water_waste"]);
  const [format, setFormat] = useState<"xlsx" | "csv" | "pdf">("xlsx");
  const [warnings, setWarnings] = useState<Warning[] | null>(null);
  const [busy, setBusy] = useState(false);
  const picks = useMemo(() => quickPicks(fiscal.fiscal_year_start), [fiscal.fiscal_year_start]);
  const pdfAllowed = type !== "audit" && !!project && ["APPROVED", "LOCKED"].includes(project.stage);

  function chooseProject(id: string) {
    const p = projects.find((x) => x.id === id);
    setProjectId(id);
    if (p) { setStart(p.start_date); setEnd(p.end_date); }
    setWarnings(null);
  }
  function pick(s: string, e: string) {
    if (!project) return;
    const cs = s < project.start_date ? project.start_date : s;
    const ce = e > project.end_date ? project.end_date : e;
    if (cs > ce) return toast.error(`That period is outside ${project.name}. Choose another project or period.`);
    if (cs !== s || ce !== e) toast.info("The period was limited to the project's dates.");
    setStart(cs); setEnd(ce); setWarnings(null);
  }
  const body = { project_id: projectId, export_type: type, format, period_start: start, period_end: end, sections: type === "audit" ? [] : sections };

  async function check() {
    setBusy(true);
    try {
      const r = await engine<{ warnings: Warning[] }>("/exports/preview", { method: "POST", json: body });
      setWarnings(r.warnings);
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  }
  async function download() {
    setBusy(true);
    try {
      await engineDownloadPost("/exports", body, `export.${format}`);
      toast.success("Export generated");
      router.refresh();
    } catch (e) { toast.error((e as Error).message, { duration: 10000 }); } finally { setBusy(false); }
  }

  if (!projects.length) return <p className="text-sm text-muted-foreground">Create a project first.</p>;
  const types = [{ key: "custom", name: "Custom", description: "Pick the data sections you need." },
    ...frameworks.map((f) => ({ ...f, name: `${f.name} layout` })),
    { key: "audit", name: "Audit export", description: "Every record with everything an auditor needs to recompute each result. Excel or CSV." }];

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader><CardTitle>1. Export type</CardTitle></CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {types.map((t) => (
            <button key={t.key} onClick={() => { setType(t.key); setWarnings(null); if (t.key === "audit" && format === "pdf") setFormat("xlsx"); }}
              className={cn("rounded-lg border p-3 text-left text-sm transition-colors hover:bg-accent/40", type === t.key && "border-primary bg-accent")}>
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-muted-foreground">{t.description}</div>
            </button>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>2. Time period</CardTitle></CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Project" htmlFor="ex-p">
              <NativeSelect id="ex-p" value={projectId} onChange={(e) => chooseProject(e.target.value)}>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.stage}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Start" htmlFor="ex-s"><Input id="ex-s" type="date" value={start} onChange={(e) => { setStart(e.target.value); setWarnings(null); }} /></Field>
            <Field label="End" htmlFor="ex-e"><Input id="ex-e" type="date" value={end} onChange={(e) => { setEnd(e.target.value); setWarnings(null); }} /></Field>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => project && pick(project.start_date, project.end_date)}>Whole project</Button>
            {picks.map((p) => <Button key={p.label} size="sm" variant="outline" onClick={() => pick(p.start, p.end)}>{p.label}</Button>)}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>3. Data and format</CardTitle></CardHeader>
        <CardContent className="grid gap-4">
          {type !== "audit" && (
            <div className="grid gap-2 sm:grid-cols-2">
              {SECTIONS.map(([k, label]) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={sections.includes(k)} onChange={(e) => { setSections((s) => e.target.checked ? [...s, k] : s.filter((x) => x !== k)); setWarnings(null); }} />
                  {label}
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {(["xlsx", "csv", "pdf"] as const).map((f) => (
              <Button key={f} size="sm" variant={format === f ? "default" : "outline"} disabled={f === "pdf" && !pdfAllowed} onClick={() => { setFormat(f); setWarnings(null); }}>
                {f === "xlsx" ? "Excel" : f === "csv" ? "CSV" : "PDF report"}
              </Button>
            ))}
          </div>
          {!pdfAllowed && type !== "audit" && <p className="text-xs text-muted-foreground">The PDF report is available once the project is approved or locked.</p>}
          {warnings && (
            <div className="grid gap-2 rounded-lg border p-3">
              <div className="text-sm font-medium">Before you export</div>
              {warnings.length === 0 && <p className="text-sm text-emerald-800">No missing or estimated data was found for this period.</p>}
              {warnings.map((w, i) => (
                <p key={i} className={cn("flex items-start gap-2 text-sm", w.level === "error" ? "text-red-800" : w.level === "warning" ? "text-amber-900" : "text-muted-foreground")}>
                  {w.level === "info" ? <Info className="mt-0.5 size-4 shrink-0" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0" />}{w.text}
                </p>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            {warnings === null ? (
              <Button onClick={check} disabled={busy || !start || !end}>{busy ? "Checking…" : "Check data"}</Button>
            ) : (
              <Button onClick={download} disabled={busy}><Download /> {busy ? "Generating…" : warnings.length ? "Export with these warnings" : "Export"}</Button>
            )}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Generated exports</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>When</TableHead><TableHead>File</TableHead><TableHead>Project</TableHead><TableHead>Period</TableHead><TableHead>Warnings</TableHead><TableHead>By</TableHead></TableRow></TableHeader>
            <TableBody>
              {history.length === 0 && <TableRow><TableCell colSpan={6} className="py-6 text-center text-muted-foreground">Nothing exported yet.</TableCell></TableRow>}
              {history.map((h) => (
                <TableRow key={h.id}>
                  <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(h.generated_at)}</TableCell>
                  <TableCell className="text-xs">{h.file_name}</TableCell>
                  <TableCell>{h.project_name}</TableCell>
                  <TableCell className="text-xs">{fmtDate(h.period_start)} – {fmtDate(h.period_end)}</TableCell>
                  <TableCell>{h.warnings.length ? <StatusBadge status="w" label={`${h.warnings.length}`} tone="amber" /> : "—"}</TableCell>
                  <TableCell className="text-xs">{h.generated_by_name}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
