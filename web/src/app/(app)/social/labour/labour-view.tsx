"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtNum } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatTile } from "@/components/app/stat-tile";
import { Missing } from "@/components/app/values";

type Month = { month: string; complete: boolean; missing_facilities: string[]; headcount: number | null; permanent: number | null; temporary: number | null; female: number | null; male: number | null; other: number | null; new_hires: number | null; departures: number | null; training_hours: number | null };
export type LabourData = {
  months: string[]; monthly: Month[]; complete: boolean; missing: Record<string, string[]>;
  headcount_avg: number | null; latest_headcount: number | null; new_hires: number | null; departures: number | null;
  turnover_rate_pct: number | null; training_hours: number | null; training_hours_per_employee: number | null; hours_worked: number | null;
};

const cell = (v: number | null) => (v === null ? <Missing /> : fmtNum(v, 0));

export function LabourView({ data, companyId, facilities, facility, canWrite }: {
  data: LabourData; companyId: string; facilities: { id: string; name: string }[]; facility: string; canWrite: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  function pickFacility(id: string) {
    const q = new URLSearchParams(params.toString());
    if (id) q.set("facility", id); else q.delete("facility");
    router.push(`${pathname}?${q}`);
  }
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const n = (k: string) => (String(f.get(k) ?? "") === "" ? null : Number(f.get(k)));
    const { error } = await createClient().from("labour_monthly").upsert({
      company_id: companyId, facility_id: String(f.get("facility_id")), month: `${f.get("month")}-01`,
      headcount_permanent: n("permanent") ?? 0, headcount_temporary: n("temporary") ?? 0, headcount_female: n("female") ?? 0,
      headcount_male: n("male") ?? 0, headcount_other: n("other") ?? 0, new_hires: n("new_hires") ?? 0, departures: n("departures") ?? 0,
      working_hours: n("working_hours"), overtime_hours: n("overtime_hours"), training_hours: n("training_hours"),
    }, { onConflict: "facility_id,month" });
    if (error) {
      return toast.error(error.message.includes("labour_breakdowns_agree")
        ? "Permanent + temporary must equal female + male + other." : error.message);
    }
    toast.success("Month saved");
    router.refresh();
  }
  return (
    <div className="grid gap-6">
      <div className="flex justify-end">
        <NativeSelect className="w-60" value={facility} onChange={(e) => pickFacility(e.target.value)} aria-label="Facility">
          <option value="">All facilities</option>{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </NativeSelect>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <StatTile label="Employees" value={data.latest_headcount === null ? null : fmtNum(data.latest_headcount, 0)} hint={data.headcount_avg !== null ? `Average ${fmtNum(data.headcount_avg, 1)} over the period` : undefined} />
        <StatTile label="Turnover" value={data.turnover_rate_pct === null ? null : fmtNum(data.turnover_rate_pct, 1)} unit="% for the period"
          hint={data.complete ? `${data.departures} departures ÷ average headcount` : "Missing months make the period figure Missing"} />
        <StatTile label="Training hours" value={data.training_hours === null ? null : fmtNum(data.training_hours, 0)}
          hint={data.training_hours_per_employee !== null ? `${fmtNum(data.training_hours_per_employee, 1)} hours per employee` : undefined} />
      </div>
      <Card>
        <CardHeader><CardTitle>Monthly headcount</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Month</TableHead><TableHead className="text-right">Permanent</TableHead><TableHead className="text-right">Temporary</TableHead><TableHead className="text-right">Female</TableHead><TableHead className="text-right">Male</TableHead><TableHead className="text-right">Hires</TableHead><TableHead className="text-right">Departures</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.monthly.map((m) => (
                <TableRow key={m.month}>
                  <TableCell>{m.month}{m.missing_facilities.length > 0 && m.headcount !== null && <div className="text-xs text-red-700">Missing: {m.missing_facilities.join(", ")}</div>}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.permanent)}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.temporary)}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.female)}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.male)}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.new_hires)}</TableCell>
                  <TableCell className="text-right tabular-nums">{cell(m.departures)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {canWrite && (
        <Card>
          <CardHeader><CardTitle>Enter or update a month</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={save} className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Field label="Facility" htmlFor="lb-f"><NativeSelect id="lb-f" name="facility_id">{facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect></Field>
              <Field label="Month" htmlFor="lb-m"><Input id="lb-m" name="month" type="month" required /></Field>
              {[["permanent", "Permanent"], ["temporary", "Temporary"], ["female", "Female"], ["male", "Male"], ["other", "Other gender"], ["new_hires", "New hires"], ["departures", "Departures"],
                ["working_hours", "Working hours"], ["overtime_hours", "Overtime hours"], ["training_hours", "Training hours"]].map(([k, l]) => (
                <Field key={k} label={l} htmlFor={`lb-${k}`}><Input id={`lb-${k}`} name={k} type="number" min={0} step={k.endsWith("hours") ? "any" : 1} /></Field>
              ))}
              <div className="flex items-end"><Button type="submit">Save month</Button></div>
            </form>
            <p className="mt-2 text-xs text-muted-foreground">Totals only: the employment-type and gender breakdowns must add up to the same headcount.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
