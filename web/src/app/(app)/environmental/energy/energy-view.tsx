"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtNum } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StackedColumns, type Series } from "@/components/charts/charts";
import { SERIES } from "@/components/charts/palette";
import { NativeSelect } from "@/components/app/native-select";
import { StatTile } from "@/components/app/stat-tile";
import { Missing } from "@/components/app/values";

export type EnergyData = {
  total_kwh: number | null;
  missing_months: string[];
  by_source_kwh: Record<string, number | null>;
  renewable_share_pct: number | null;
  by_facility_kwh: Record<string, number>;
  monthly: ({ month: string; missing: string[] } & Record<string, number | null | string | string[]>)[];
  unconverted: { record_id: string; terminal_key: string; facility: string; quantity: number; unit: string }[];
  denominators: { kind: string; value: number; unit: string; facility_id: string | null; facility: string | null }[];
  intensity: { kind: string; denominator: number | null; denominator_unit: string | null; value: number | null } | null;
};

const SOURCES: Series[] = [
  { key: "electricity", label: "Grid electricity", color: SERIES[0] },
  { key: "fuels_stationary", label: "Fuels, stationary", color: SERIES[1] },
  { key: "fuels_mobile", label: "Fuels, vehicles", color: SERIES[2] },
  { key: "heat_steam_cooling", label: "Purchased heat/steam/cooling", color: SERIES[3] },
  { key: "renewable", label: "On-site renewable", color: SERIES[4] },
];
const KIND_LABEL: Record<string, string> = {
  employees: "employee", production_mass: "tonne of production", production_units: "unit of production", revenue: "BDT of revenue",
};

function energyText(kwh: number | null): { value: string | null; unit: string } {
  if (kwh === null) return { value: null, unit: "" };
  if (kwh >= 1e6) return { value: fmtNum(kwh / 1e6, 2), unit: "GWh" };
  if (kwh >= 1e3) return { value: fmtNum(kwh / 1e3, 1), unit: "MWh" };
  return { value: fmtNum(kwh, 0), unit: "kWh" };
}

export function EnergyView({ data, kind, projectId, companyId, facilities, canWrite }: {
  data: EnergyData; kind: string; projectId: string; companyId: string; facilities: { id: string; name: string }[]; canWrite: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const reported = SOURCES.filter((s) => data.by_source_kwh[s.key] !== null);
  const total = energyText(data.total_kwh);
  const intensity = data.intensity;

  function setKind(k: string) {
    const q = new URLSearchParams(params.toString());
    q.set("denominator", k);
    router.push(`${pathname}?${q}`);
  }

  return (
    <div className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-3">
        <StatTile label="Total energy" value={total.value} unit={total.unit}
          hint={data.missing_months.length > 0
            ? `Covers reported months only: ${data.missing_months.length} month${data.missing_months.length > 1 ? "s" : ""} Missing`
            : "Fuels are converted with the matched factor's cited net calorific value"} />
        <StatTile label="Renewable share" value={data.renewable_share_pct === null ? null : fmtNum(data.renewable_share_pct, 1)} unit="%" hint="On-site generation ÷ total energy" />
        <StatTile label="Intensity" value={intensity?.value === null || intensity?.value === undefined ? null : fmtNum(intensity.value, 2)}
          unit={`kWh / ${KIND_LABEL[kind]}`}
          hint={intensity?.denominator ? `Denominator ${fmtNum(intensity.denominator, 2)} ${intensity.denominator_unit ?? ""}` : "Set a denominator below"}>
          <NativeSelect className="mt-2" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Intensity denominator">
            {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>per {l}</option>)}
          </NativeSelect>
        </StatTile>
      </div>

      {reported.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Monthly energy by source (kWh)</CardTitle></CardHeader>
          <CardContent>
            <StackedColumns data={data.monthly as never} x="month" series={reported} unit="kWh" />
            <Table className="mt-4">
              <TableHeader>
                <TableRow><TableHead>Month</TableHead>{reported.map((s) => <TableHead key={s.key} className="text-right">{s.label}</TableHead>)}</TableRow>
              </TableHeader>
              <TableBody>
                {data.monthly.map((m) => (
                  <TableRow key={m.month}>
                    <TableCell>{m.month}</TableCell>
                    {reported.map((s) => (
                      <TableCell key={s.key} className="text-right tabular-nums">
                        {m[s.key] === null ? <Missing /> : `${fmtNum(m[s.key] as number, 0)} kWh`}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>By facility</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableBody>
                {Object.entries(data.by_facility_kwh).map(([f, v]) => (
                  <TableRow key={f}><TableCell>{f}</TableCell><TableCell className="text-right tabular-nums">{fmtNum(v, 0)} kWh</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
            {data.unconverted.length > 0 && (
              <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                {data.unconverted.length} fuel record{data.unconverted.length > 1 ? "s are" : " is"} not in the total: the fuel is not categorized yet,
                or its emission factor has no cited energy-content conversion. They are excluded, not counted as zero.
              </p>
            )}
          </CardContent>
        </Card>
        <DenominatorEditor data={data} projectId={projectId} companyId={companyId} facilities={facilities} canWrite={canWrite} />
      </div>
    </div>
  );
}

function DenominatorEditor({ data, projectId, companyId, facilities, canWrite }: {
  data: EnergyData; projectId: string; companyId: string; facilities: { id: string; name: string }[]; canWrite: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const facility = String(f.get("facility_id") || "") || null;
    const kind = String(f.get("kind"));
    const supabase = createClient();
    setBusy(true);
    let q = supabase.from("denominators").delete().eq("project_id", projectId).eq("kind", kind);
    q = facility ? q.eq("facility_id", facility) : q.is("facility_id", null);
    await q;
    const { error } = await supabase.from("denominators").insert({
      company_id: companyId, project_id: projectId, facility_id: facility, kind, value: Number(f.get("value")), unit: String(f.get("unit")),
    });
    setBusy(false);
    if (error) return toast.error(error.message);
    toast.success("Denominator saved; intensity recalculated");
    router.refresh();
  }
  return (
    <Card>
      <CardHeader><CardTitle>Intensity denominators</CardTitle></CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <Table>
          <TableHeader><TableRow><TableHead>Scope</TableHead><TableHead>Denominator</TableHead><TableHead className="text-right">Value</TableHead></TableRow></TableHeader>
          <TableBody>
            {data.denominators.length === 0 && <TableRow><TableCell colSpan={3} className="text-muted-foreground">None set yet.</TableCell></TableRow>}
            {data.denominators.map((d, i) => (
              <TableRow key={i}><TableCell>{d.facility ?? "Whole company"}</TableCell><TableCell>{KIND_LABEL[d.kind]}</TableCell>
                <TableCell className="text-right tabular-nums">{fmtNum(d.value, 2)} {d.unit}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
        {canWrite && (
          <form onSubmit={save} className="grid gap-2 sm:grid-cols-2">
            <NativeSelect name="facility_id" aria-label="Facility"><option value="">Whole company</option>{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect>
            <NativeSelect name="kind" aria-label="Kind">{Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</NativeSelect>
            <Input name="value" type="number" step="any" min="0" placeholder="Value for the project period" required />
            <Input name="unit" placeholder="Unit, e.g. t, pieces, employees, BDT" required />
            <div><Button size="sm" type="submit" disabled={busy}>Save denominator</Button></div>
          </form>
        )}
        <p className="text-xs text-muted-foreground">A company-wide value is used when set; otherwise facility values are summed (all facilities with energy data need one).</p>
      </CardContent>
    </Card>
  );
}
