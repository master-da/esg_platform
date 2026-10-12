"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

type Permit = { id: string; facility_id: string | null; permit_type: string; permit_number: string | null; issuing_authority: string; issue_date: string | null; expiry_date: string | null; conditions: string | null; reminder_lead_days: number; status: string; facilities: { name: string } | null };

function alertFor(p: Permit) {
  if (!p.expiry_date || !["active", "renewal_in_progress"].includes(p.status)) return null;
  const days = Math.round((new Date(p.expiry_date).getTime() - new Date(new Date().toDateString()).getTime()) / 86400000);
  if (days < 0) return { label: `✕ Expired ${-days} days ago`, tone: "red" as const };
  if (days <= p.reminder_lead_days) return { label: `! Renew: ${days} days left`, tone: "amber" as const };
  return null;
}

export function PermitsView({ companyId, permits, facilities, canWrite }: { companyId: string; permits: Permit[]; facilities: { id: string; name: string }[]; canWrite: boolean }) {
  const router = useRouter();
  const [editing, setEditing] = useState<Permit | "new" | null>(null);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "").trim() || null;
    const row = { company_id: companyId, facility_id: v("facility_id"), permit_type: v("permit_type"), permit_number: v("permit_number"),
      issuing_authority: v("issuing_authority"), issue_date: v("issue_date"), expiry_date: v("expiry_date"), conditions: v("conditions"),
      reminder_lead_days: Number(v("reminder_lead_days") ?? 60), status: v("status") ?? "active" };
    const supabase = createClient();
    const { error } = editing && editing !== "new" ? await supabase.from("permits").update(row).eq("id", editing.id) : await supabase.from("permits").insert(row);
    if (error) return toast.error(error.message);
    toast.success("Permit saved");
    setEditing(null);
    router.refresh();
  }
  const cur = editing && editing !== "new" ? editing : null;
  return (
    <div className="grid gap-4">
      {canWrite && <div><Button onClick={() => setEditing("new")}>Add permit</Button></div>}
      {editing && (
        <Card>
          <CardHeader><CardTitle>{cur ? "Edit permit" : "New permit"}</CardTitle></CardHeader>
          <CardContent>
            <form key={cur?.id ?? "new"} onSubmit={save} className="grid gap-3 sm:grid-cols-3">
              <Field label="Permit type" htmlFor="pm-type"><Input id="pm-type" name="permit_type" defaultValue={cur?.permit_type} placeholder="e.g. Environmental Clearance Certificate" required /></Field>
              <Field label="Number" htmlFor="pm-no"><Input id="pm-no" name="permit_number" defaultValue={cur?.permit_number ?? ""} /></Field>
              <Field label="Issuing authority" htmlFor="pm-auth"><Input id="pm-auth" name="issuing_authority" defaultValue={cur?.issuing_authority} required /></Field>
              <Field label="Facility" htmlFor="pm-fac"><NativeSelect id="pm-fac" name="facility_id" defaultValue={cur?.facility_id ?? ""}><option value="">Whole company</option>{facilities.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</NativeSelect></Field>
              <Field label="Issue date" htmlFor="pm-iss"><Input id="pm-iss" name="issue_date" type="date" defaultValue={cur?.issue_date ?? ""} /></Field>
              <Field label="Expiry date" htmlFor="pm-exp"><Input id="pm-exp" name="expiry_date" type="date" defaultValue={cur?.expiry_date ?? ""} /></Field>
              <Field label="Reminder lead time (days)" htmlFor="pm-lead"><Input id="pm-lead" name="reminder_lead_days" type="number" min={0} max={730} defaultValue={cur?.reminder_lead_days ?? 60} /></Field>
              <Field label="Status" htmlFor="pm-st"><NativeSelect id="pm-st" name="status" defaultValue={cur?.status ?? "active"}><option value="active">Active</option><option value="renewal_in_progress">Renewal in progress</option><option value="expired">Expired</option><option value="cancelled">Cancelled</option></NativeSelect></Field>
              <div className="sm:col-span-3"><Field label="Conditions" htmlFor="pm-cond"><Textarea id="pm-cond" name="conditions" rows={2} defaultValue={cur?.conditions ?? ""} /></Field></div>
              <div className="flex gap-2"><Button type="submit">Save</Button><Button type="button" variant="outline" onClick={() => setEditing(null)}>Cancel</Button></div>
            </form>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Permit</TableHead><TableHead>Authority</TableHead><TableHead>Facility</TableHead><TableHead>Issued</TableHead><TableHead>Expires</TableHead><TableHead>Reminder</TableHead><TableHead>Status</TableHead>{canWrite && <TableHead />}</TableRow></TableHeader>
            <TableBody>
              {permits.length === 0 && <TableRow><TableCell colSpan={8} className="py-6 text-center text-muted-foreground">No permits recorded.</TableCell></TableRow>}
              {permits.map((p) => {
                const a = alertFor(p);
                return (
                  <TableRow key={p.id}>
                    <TableCell>{p.permit_type}<div className="text-xs text-muted-foreground">{p.permit_number}</div></TableCell>
                    <TableCell className="text-sm">{p.issuing_authority}</TableCell>
                    <TableCell>{p.facilities?.name ?? "Whole company"}</TableCell>
                    <TableCell className="text-xs">{fmtDate(p.issue_date)}</TableCell>
                    <TableCell className="text-xs">{p.expiry_date ? fmtDate(p.expiry_date) : "No expiry"}</TableCell>
                    <TableCell className="text-xs">{p.reminder_lead_days} days before</TableCell>
                    <TableCell className="space-y-1">{a ? <StatusBadge status="alert" label={a.label} tone={a.tone} /> : <StatusBadge status={p.status} label={p.status.replace("_", " ")} tone={p.status === "active" ? "green" : "gray"} />}</TableCell>
                    {canWrite && <TableCell><Button size="xs" variant="ghost" onClick={() => setEditing(p)}>Edit</Button></TableCell>}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
