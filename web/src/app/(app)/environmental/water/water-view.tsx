"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { createClient } from "@/lib/supabase/client";
import { fmtDate, fmtNum } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StackedColumns } from "@/components/charts/charts";
import { SERIES } from "@/components/charts/palette";
import { Field } from "@/components/app/field";
import { ManualEntryForm, type TerminalColumn } from "@/components/app/manual-entry-form";
import { NativeSelect } from "@/components/app/native-select";
import { StatTile } from "@/components/app/stat-tile";
import { StatusBadge } from "@/components/app/status-badge";
import { Missing } from "@/components/app/values";

export type WaterData = {
  withdrawal_m3: number | null; discharge_m3: number | null; consumption_m3: number | null; consumption_basis: string;
  by_source: Record<string, number>; by_destination: Record<string, number>;
  monthly: { month: string; withdrawal: number | null; discharge: number | null; missing: string[] }[];
  records: { id: string; terminal_key: string; facility: string; period_start: string; period_end: string; normalized_quantity: number; attributes: Record<string, string>; review_status: string; source_type: string }[];
  verification: { verified: number; pending: number };
};
type Sample = { id: string; sample_date: string; parameter_key: string; value: number; destination: string | null; lab_name: string | null; lab_report_ref: string | null; result: string; threshold_snapshot: { min_value: number | null; max_value: number | null; regulation: string; status: string } | null; facilities: { name: string } | null };
type Threshold = { id: string; parameter_key: string; destination: string | null; min_value: number | null; max_value: number | null; warning_band_pct: number; regulator: string; regulation: string; source_url: string; status: string; valid_from: string; valid_to: string | null; version: number };

export function WaterView(props: {
  data: WaterData | null; projectId: string | null; companyId: string; terminals: { key: string; name: string; config: { columns: TerminalColumn[] } }[];
  facilities: { id: string; name: string }[]; samples: Sample[]; parameters: { key: string; name: string; unit: string }[]; thresholds: Threshold[];
  canWrite: boolean; canWriteSamples: boolean; canEditLimits: boolean;
}) {
  return (
    <Tabs defaultValue="flows">
      <TabsList>
        <TabsTrigger value="flows">Withdrawal & discharge</TabsTrigger>
        <TabsTrigger value="quality">Water quality / ETP</TabsTrigger>
      </TabsList>
      <TabsContent value="flows"><Flows {...props} /></TabsContent>
      <TabsContent value="quality"><Quality {...props} /></TabsContent>
    </Tabs>
  );
}

function Flows({ data, projectId, terminals, facilities, canWrite }: Parameters<typeof WaterView>[0]) {
  const [logKey, setLogKey] = useState("water_withdrawal");
  if (!data || !projectId) return <p className="text-sm text-muted-foreground">Create a project to log water data.</p>;
  const t = terminals.find((x) => x.key === logKey);
  return (
    <div className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-3">
        <StatTile label="Withdrawal" value={data.withdrawal_m3 === null ? null : fmtNum(data.withdrawal_m3, 0)} unit="m³" />
        <StatTile label="Discharge" value={data.discharge_m3 === null ? null : fmtNum(data.discharge_m3, 0)} unit="m³" />
        <StatTile label="Consumption" value={data.consumption_m3 === null ? null : fmtNum(data.consumption_m3, 0)} unit="m³" hint={data.consumption_basis} />
      </div>
      <Card>
        <CardHeader><CardTitle>Monthly withdrawal and discharge (m³)</CardTitle></CardHeader>
        <CardContent>
          <StackedColumns data={data.monthly.map((m) => ({ month: m.month, withdrawal: m.withdrawal }))} x="month"
            series={[{ key: "withdrawal", label: "Withdrawal", color: SERIES[0] }]} unit="m³" height={200} />
          <Table className="mt-4">
            <TableHeader><TableRow><TableHead>Month</TableHead><TableHead className="text-right">Withdrawal</TableHead><TableHead className="text-right">Discharge</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.monthly.map((m) => (
                <TableRow key={m.month}>
                  <TableCell>{m.month}</TableCell>
                  <TableCell className="text-right tabular-nums">{m.withdrawal === null ? <Missing /> : `${fmtNum(m.withdrawal, 0)} m³`}</TableCell>
                  <TableCell className="text-right tabular-nums">{m.discharge === null ? <Missing /> : `${fmtNum(m.discharge, 0)} m³`}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-muted-foreground">Missing months are shown as Missing, never as 0.</p>
        </CardContent>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Withdrawal by source</CardTitle></CardHeader>
          <CardContent><Table><TableBody>{Object.entries(data.by_source).map(([k, v]) => <TableRow key={k}><TableCell>{k}</TableCell><TableCell className="text-right tabular-nums">{fmtNum(v, 0)} m³</TableCell></TableRow>)}</TableBody></Table></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Discharge by destination</CardTitle></CardHeader>
          <CardContent><Table><TableBody>{Object.entries(data.by_destination).map(([k, v]) => <TableRow key={k}><TableCell>{k}</TableCell><TableCell className="text-right tabular-nums">{fmtNum(v, 0)} m³</TableCell></TableRow>)}</TableBody></Table></CardContent>
        </Card>
      </div>
      {canWrite && t && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Log a record</CardTitle>
            <NativeSelect className="w-48" value={logKey} onChange={(e) => setLogKey(e.target.value)} aria-label="Record type">
              <option value="water_withdrawal">Withdrawal</option><option value="water_discharge">Discharge</option>
            </NativeSelect>
          </CardHeader>
          <CardContent>
            <ManualEntryForm key={logKey} projectId={projectId} terminalKey={logKey} columns={t.config.columns} facilities={facilities.map((f) => f.name)} />
            <p className="mt-2 text-xs text-muted-foreground">Bulk data: use the Water withdrawal / discharge templates on the project&apos;s category pages.</p>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle>Records ({data.records.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Facility</TableHead><TableHead>Period</TableHead><TableHead>Source / destination</TableHead><TableHead className="text-right">Quantity</TableHead><TableHead>Verification</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.records.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.terminal_key === "water_withdrawal" ? "Withdrawal" : "Discharge"}</TableCell>
                  <TableCell>{r.facility}</TableCell>
                  <TableCell className="text-xs">{fmtDate(r.period_start)} – {fmtDate(r.period_end)}</TableCell>
                  <TableCell>{r.attributes.source ?? r.attributes.destination}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmtNum(r.normalized_quantity, 2)} m³</TableCell>
                  <TableCell><StatusBadge status={r.review_status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Quality({ companyId, facilities, samples, parameters, thresholds, canWriteSamples, canEditLimits }: Parameters<typeof WaterView>[0]) {
  const router = useRouter();
  const unit = new Map(parameters.map((p) => [p.key, p.unit]));
  const name = new Map(parameters.map((p) => [p.key, p.name]));
  const limit = (t: { min_value: number | null; max_value: number | null } | null) =>
    !t ? "No threshold configured" : t.min_value !== null && t.max_value !== null ? `${t.min_value} – ${t.max_value}` : t.max_value !== null ? `≤ ${t.max_value}` : `≥ ${t.min_value}`;

  async function addSample(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const { data, error } = await createClient().from("wq_samples").insert({
      company_id: companyId, facility_id: String(f.get("facility_id")), sample_date: String(f.get("sample_date")),
      parameter_key: String(f.get("parameter_key")), value: Number(f.get("value")),
      destination: String(f.get("destination") || "") || null, lab_name: String(f.get("lab_name") || "") || null,
      lab_report_ref: String(f.get("lab_report_ref") || "") || null,
    }).select("result").single();
    if (error) return toast.error(error.message);
    toast.success(`Saved: ${data.result.replace("_", " ")}`);
    (e.target as HTMLFormElement).reset();
    router.refresh();
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader><CardTitle>Lab results</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Facility</TableHead><TableHead>Parameter</TableHead><TableHead className="text-right">Result</TableHead><TableHead>Limit</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
            <TableBody>
              {samples.length === 0 && <TableRow><TableCell colSpan={6} className="py-6 text-center text-muted-foreground">No lab results yet.</TableCell></TableRow>}
              {samples.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>{fmtDate(s.sample_date)}</TableCell>
                  <TableCell>{s.facilities?.name}</TableCell>
                  <TableCell>{name.get(s.parameter_key) ?? s.parameter_key}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmtNum(s.value, 3)} {unit.get(s.parameter_key)}</TableCell>
                  <TableCell className="text-xs">{limit(s.threshold_snapshot)}{s.threshold_snapshot && <div className="text-muted-foreground">{s.threshold_snapshot.regulation}{s.threshold_snapshot.status === "NEEDS_REVIEW" ? " · needs review" : ""}</div>}</TableCell>
                  <TableCell><StatusBadge status={s.result} label={s.result === "NO_THRESHOLD" ? "No threshold" : s.result === "FAIL" ? "✕ FAIL" : s.result === "WARNING" ? "! WARNING" : "✓ PASS"} tone={s.result === "NO_THRESHOLD" ? "gray" : undefined} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-muted-foreground">Each result is checked against the threshold valid on its sample date. New parameters and limit updates are data changes; no deployment is needed.</p>
        </CardContent>
      </Card>
      {canWriteSamples && (
        <Card>
          <CardHeader><CardTitle>Record a lab result</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={addSample} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Facility" htmlFor="wq-fac"><NativeSelect id="wq-fac" name="facility_id">{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect></Field>
              <Field label="Sample date" htmlFor="wq-date"><Input id="wq-date" name="sample_date" type="date" required /></Field>
              <Field label="Parameter" htmlFor="wq-param"><NativeSelect id="wq-param" name="parameter_key">{parameters.map((p) => <option key={p.key} value={p.key}>{p.name} ({p.unit})</option>)}</NativeSelect></Field>
              <Field label="Result" htmlFor="wq-value"><Input id="wq-value" name="value" type="number" step="any" required /></Field>
              <Field label="Discharge destination (optional)" htmlFor="wq-dest"><Input id="wq-dest" name="destination" /></Field>
              <Field label="Lab (optional)" htmlFor="wq-lab"><Input id="wq-lab" name="lab_name" /></Field>
              <Field label="Lab report ref (optional)" htmlFor="wq-ref"><Input id="wq-ref" name="lab_report_ref" /></Field>
              <div className="flex items-end"><Button type="submit">Save result</Button></div>
            </form>
          </CardContent>
        </Card>
      )}
      <Thresholds parameters={parameters} thresholds={thresholds} canEdit={canEditLimits} />
    </div>
  );
}

function Thresholds({ parameters, thresholds, canEdit }: { parameters: { key: string; name: string; unit: string }[]; thresholds: Threshold[]; canEdit: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const name = new Map(parameters.map((p) => [p.key, `${p.name} (${p.unit})`]));
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "").trim() || null;
    try {
      await engine("/reference/wq-thresholds", { method: "POST", json: {
        parameter_key: v("parameter_key"), destination: v("destination"), min_value: v("min_value"), max_value: v("max_value"),
        warning_band_pct: v("warning_band_pct") ?? "10", regulator: v("regulator"), regulation: v("regulation"),
        source_url: v("source_url"), status: v("status"), valid_from: v("valid_from"), valid_to: v("valid_to"),
      } });
      toast.success("Threshold saved");
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Thresholds in force</CardTitle>
        {canEdit && <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>{open ? "Cancel" : "Add threshold"}</Button>}
      </CardHeader>
      <CardContent className="grid gap-4">
        {thresholds.length === 0 ? (
          <p className="text-sm text-amber-800">
            No regulatory limits are configured. Limits must come from the official text (e.g. the Environment Conservation Rules 2023 schedules);
            they are not pre-filled because no verifiable copy of the gazette was available. Until a limit is added, results show &quot;No threshold&quot;.
          </p>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>Parameter</TableHead><TableHead>Limit</TableHead><TableHead>Warning band</TableHead><TableHead>Source</TableHead><TableHead>Valid</TableHead></TableRow></TableHeader>
            <TableBody>
              {thresholds.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{name.get(t.parameter_key)}{t.destination && <div className="text-xs text-muted-foreground">{t.destination}</div>}</TableCell>
                  <TableCell className="tabular-nums">{t.min_value ?? "—"} – {t.max_value ?? "—"}</TableCell>
                  <TableCell>{t.warning_band_pct}% of limit</TableCell>
                  <TableCell className="text-xs"><a className="text-primary hover:underline" href={t.source_url} target="_blank" rel="noreferrer">{t.regulator}: {t.regulation}</a> <StatusBadge status={t.status} /></TableCell>
                  <TableCell className="text-xs">{fmtDate(t.valid_from)} – {t.valid_to ? fmtDate(t.valid_to) : "open"} · v{t.version}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {open && (
          <form onSubmit={add} className="grid gap-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-3">
            <Field label="Parameter" htmlFor="th-p"><NativeSelect id="th-p" name="parameter_key">{parameters.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}</NativeSelect></Field>
            <Field label="Minimum (optional)" htmlFor="th-min"><Input id="th-min" name="min_value" type="number" step="any" /></Field>
            <Field label="Maximum (optional)" htmlFor="th-max"><Input id="th-max" name="max_value" type="number" step="any" /></Field>
            <Field label="Destination (optional)" htmlFor="th-dest"><Input id="th-dest" name="destination" /></Field>
            <Field label="Warning band % (platform policy)" htmlFor="th-band"><Input id="th-band" name="warning_band_pct" type="number" defaultValue={10} /></Field>
            <Field label="Status" htmlFor="th-status"><NativeSelect id="th-status" name="status"><option value="NEEDS_REVIEW">NEEDS_REVIEW</option><option value="VERIFIED">VERIFIED</option></NativeSelect></Field>
            <Field label="Regulator" htmlFor="th-reg"><Input id="th-reg" name="regulator" placeholder="Department of Environment" required /></Field>
            <Field label="Regulation and schedule" htmlFor="th-rule"><Input id="th-rule" name="regulation" placeholder="ECR 2023, Schedule …" required /></Field>
            <Field label="Source URL" htmlFor="th-url"><Input id="th-url" name="source_url" type="url" required /></Field>
            <Field label="Valid from" htmlFor="th-from"><Input id="th-from" name="valid_from" type="date" required /></Field>
            <Field label="Valid to (optional)" htmlFor="th-to"><Input id="th-to" name="valid_to" type="date" /></Field>
            <div className="flex items-end"><Button type="submit">Save threshold</Button></div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
