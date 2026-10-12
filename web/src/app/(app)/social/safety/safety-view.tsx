"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtDate, fmtNum } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { StackedColumns, TrendLines } from "@/components/charts/charts";
import { SERIES } from "@/components/charts/palette";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatTile } from "@/components/app/stat-tile";
import { StatusBadge } from "@/components/app/status-badge";

type Incident = { id: string; occurred_on: string; facility: string; type: string; severity: string; workers_affected: number; lost_time: boolean; lost_days: number; fatalities: number; root_cause: string | null; status: string };
export type SafetyData = {
  incidents: Incident[]; by_type: Record<string, number>; lti_count: number; fatalities: number; lost_days: number;
  hours_worked: number | null; multiplier: number; ltifr: number | null; injury_rate: number | null;
  hours_missing: Record<string, string[]>; trend: { month: string; incidents: number; lti: number; ltifr: number | null }[];
};
const TYPES = ["injury", "fatality", "near_miss", "fire", "chemical", "environmental", "other"];

export function SafetyView({ data, companyId, facilities, canWrite }: { data: SafetyData; companyId: string; facilities: { id: string; name: string }[]; canWrite: boolean }) {
  const router = useRouter();
  const per = `per ${fmtNum(data.multiplier, 0)} hours`;
  async function log(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const type = String(f.get("type"));
    const lostTime = f.get("lost_time") === "on";
    const { error } = await createClient().from("incidents").insert({
      company_id: companyId, facility_id: String(f.get("facility_id")), occurred_on: String(f.get("occurred_on")), type,
      severity: String(f.get("severity")), workers_affected: Number(f.get("workers_affected") || 0), lost_time: lostTime,
      lost_days: lostTime ? Number(f.get("lost_days") || 0) : 0, fatalities: type === "fatality" ? Number(f.get("fatalities") || 1) : 0,
      root_cause: String(f.get("root_cause") || "") || null, description: String(f.get("description") || "") || null,
    });
    if (error) return toast.error(error.message);
    toast.success("Incident logged");
    (e.target as HTMLFormElement).reset();
    router.refresh();
  }
  const hoursGap = Object.entries(data.hours_missing);
  return (
    <div className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-5">
        <StatTile label="LTIFR" value={data.ltifr === null ? null : fmtNum(data.ltifr, 2)} hint={data.ltifr === null ? "Needs complete hours worked" : per} />
        <StatTile label="Injury frequency" value={data.injury_rate === null ? null : fmtNum(data.injury_rate, 2)} hint={per} />
        <StatTile label="Lost-time injuries" value={String(data.lti_count)} />
        <StatTile label="Fatalities" value={String(data.fatalities)} />
        <StatTile label="Lost days" value={String(data.lost_days)} />
      </div>
      {hoursGap.length > 0 && (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
          Hours worked are missing for {hoursGap.map(([f, m]) => `${f} (${m.join(", ")})`).join("; ")}, so frequency rates are shown as Missing.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Incidents per month</CardTitle></CardHeader>
          <CardContent><StackedColumns data={data.trend} x="month" series={[{ key: "incidents", label: "Incidents", color: SERIES[0] }]} digits={0} height={200} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>LTIFR by month ({per})</CardTitle></CardHeader>
          <CardContent><TrendLines data={data.trend} x="month" series={[{ key: "ltifr", label: "LTIFR", color: SERIES[0] }]} height={200} /></CardContent>
        </Card>
      </div>
      {canWrite && (
        <Card>
          <CardHeader><CardTitle>Log an incident</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={log} className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
              <Field label="Facility" htmlFor="in-f"><NativeSelect id="in-f" name="facility_id">{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect></Field>
              <Field label="Date" htmlFor="in-d"><Input id="in-d" name="occurred_on" type="date" required /></Field>
              <Field label="Type" htmlFor="in-t"><NativeSelect id="in-t" name="type">{TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</NativeSelect></Field>
              <Field label="Severity" htmlFor="in-s"><NativeSelect id="in-s" name="severity"><option>minor</option><option>moderate</option><option>major</option><option>critical</option></NativeSelect></Field>
              <Field label="Workers affected" htmlFor="in-w"><Input id="in-w" name="workers_affected" type="number" min={0} defaultValue={0} /></Field>
              <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" name="lost_time" /> Caused lost time</label>
              <Field label="Lost days" htmlFor="in-l"><Input id="in-l" name="lost_days" type="number" min={0} defaultValue={0} /></Field>
              <Field label="Fatalities (fatality only)" htmlFor="in-fa"><Input id="in-fa" name="fatalities" type="number" min={0} /></Field>
              <Field label="Root cause" htmlFor="in-r"><Input id="in-r" name="root_cause" /></Field>
              <div className="sm:col-span-3"><Field label="Description (no names or personal details)" htmlFor="in-desc"><Textarea id="in-desc" name="description" rows={2} /></Field></div>
              <div className="flex items-end"><Button type="submit">Log incident</Button></div>
            </form>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle>Incidents ({data.incidents.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Facility</TableHead><TableHead>Type</TableHead><TableHead>Severity</TableHead><TableHead>Lost time</TableHead><TableHead className="text-right">Lost days</TableHead><TableHead>Root cause</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.incidents.map((i) => (
                <TableRow key={i.id}>
                  <TableCell>{fmtDate(i.occurred_on)}</TableCell>
                  <TableCell>{i.facility}</TableCell>
                  <TableCell className="capitalize">{i.type.replace("_", " ")}</TableCell>
                  <TableCell><StatusBadge status={i.severity} label={i.severity} tone={i.severity === "critical" || i.severity === "major" ? "red" : i.severity === "moderate" ? "amber" : "gray"} /></TableCell>
                  <TableCell>{i.lost_time ? "Yes" : "No"}</TableCell>
                  <TableCell className="text-right tabular-nums">{i.lost_days}</TableCell>
                  <TableCell className="text-xs">{i.root_cause}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
