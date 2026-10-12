"use client";

import { AlertTriangle } from "lucide-react";
import { fmtDate, fmtNum } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BreakdownBars } from "@/components/charts/charts";
import { SERIES } from "@/components/charts/palette";
import { ManualEntryForm, type TerminalColumn } from "@/components/app/manual-entry-form";
import { StatTile } from "@/components/app/stat-tile";
import { StatusBadge } from "@/components/app/status-badge";
import { Missing } from "@/components/app/values";

export type WasteData = {
  total_t: number | null; hazardous_t: number | null; non_hazardous_t: number | null; recycled_t: number | null;
  recycling_rate_pct: number | null; recycling_definition: string; co2e_t: number | null;
  by_treatment: Record<string, number>; by_type: Record<string, number>;
  records: { id: string; facility: string; period_start: string; period_end: string; quantity_t: number; hazardous: boolean; supplier_name: string | null; attributes: Record<string, string>; calc_status: string | null; co2e_t: number | null }[];
  missing: { facility: string; missing_months: string[] }[];
};

/** Hazardous waste is visually distinct in every view: icon + label + red ring, never colour alone. */
export function HazardBadge({ hazardous }: { hazardous: boolean }) {
  return hazardous ? (
    <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-1.5 py-0.5 text-xs font-semibold text-red-800 ring-1 ring-red-300 ring-inset">
      <AlertTriangle className="size-3" /> Hazardous
    </span>
  ) : <span className="text-xs text-muted-foreground">Non-hazardous</span>;
}

export function WasteView({ data, projectId, columns, facilities, canWrite }: {
  data: WasteData; projectId: string; columns: TerminalColumn[]; facilities: string[]; canWrite: boolean;
}) {
  return (
    <div className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-4">
        <StatTile label="Total waste" value={data.total_t === null ? null : fmtNum(data.total_t, 2)} unit="t" />
        <StatTile label="Hazardous" value={data.hazardous_t === null ? null : fmtNum(data.hazardous_t, 2)} unit="t"
          hint={data.non_hazardous_t !== null ? `Non-hazardous ${fmtNum(data.non_hazardous_t, 2)} t` : undefined} />
        <StatTile label="Recycling rate" value={data.recycling_rate_pct === null ? null : fmtNum(data.recycling_rate_pct, 1)} unit="%" hint={data.recycling_definition} />
        <StatTile label="Emissions (Scope 3, 3.5)" value={data.co2e_t === null ? null : fmtNum(data.co2e_t, 3)} unit="t CO₂e" hint="Calculated rows only" />
      </div>
      {data.missing.length > 0 && (
        <p className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800">
          Missing months: {data.missing.map((m) => `${m.facility} (${m.missing_months.join(", ")})`).join("; ")}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>By treatment (t)</CardTitle></CardHeader>
          <CardContent><BreakdownBars data={Object.entries(data.by_treatment).map(([label, value]) => ({ label, value }))} color={SERIES[0]} unit="t" /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>By waste type (t)</CardTitle></CardHeader>
          <CardContent><BreakdownBars data={Object.entries(data.by_type).map(([label, value]) => ({ label, value }))} color={SERIES[0]} unit="t" /></CardContent>
        </Card>
      </div>
      {canWrite && (
        <Card>
          <CardHeader><CardTitle>Record waste</CardTitle></CardHeader>
          <CardContent><ManualEntryForm projectId={projectId} terminalKey="s3_c05" columns={columns} facilities={facilities} /></CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle>Records ({data.records.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Facility</TableHead><TableHead>Period</TableHead><TableHead>Waste type</TableHead><TableHead>Hazard</TableHead><TableHead>Treatment</TableHead><TableHead>Contractor</TableHead><TableHead className="text-right">Quantity</TableHead><TableHead className="text-right">t CO₂e</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.records.map((r) => (
                <TableRow key={r.id} className={r.hazardous ? "bg-red-50/50" : undefined}>
                  <TableCell>{r.facility}</TableCell>
                  <TableCell className="text-xs">{fmtDate(r.period_start)} – {fmtDate(r.period_end)}</TableCell>
                  <TableCell>{r.attributes.waste_type}</TableCell>
                  <TableCell><HazardBadge hazardous={r.hazardous} /></TableCell>
                  <TableCell>{r.attributes.treatment}</TableCell>
                  <TableCell>{r.supplier_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmtNum(r.quantity_t, 3)} t</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.calc_status === "CALCULATED" ? fmtNum(r.co2e_t, 4) : r.calc_status ? <Missing label="UNKNOWN" /> : <StatusBadge status="NEEDS" label="Not categorized" />}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
