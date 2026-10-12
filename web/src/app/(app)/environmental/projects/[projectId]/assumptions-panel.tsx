"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

export type Assumption = { id: string; category: string; statement: string; created_at: string; profiles: { full_name: string | null } | null };
export type Verification = { id: string; verifier: string; standard: string; assurance_level: string; statement_date: string; scope: string };

/** Assumptions Register (feeds the report's assumptions & limitations) and third-party assurance records. */
export function AssumptionsPanel({ companyId, projectId, assumptions, verifications, canWrite, isInternal }: {
  companyId: string; projectId: string; assumptions: Assumption[]; verifications: Verification[]; canWrite: boolean; isInternal: boolean;
}) {
  const router = useRouter();
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const { error } = await createClient().from("assumptions").insert({ company_id: companyId, project_id: projectId,
      category: String(f.get("category")), statement: String(f.get("statement")) });
    if (error) return toast.error(error.message);
    (e.target as HTMLFormElement).reset();
    router.refresh();
  }
  async function addVerification(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const { error } = await createClient().from("verifications").insert({ company_id: companyId, project_id: projectId,
      verifier: String(f.get("verifier")), standard: String(f.get("standard")), assurance_level: String(f.get("assurance_level")),
      statement_date: String(f.get("statement_date")), scope: String(f.get("scope")) });
    if (error) return toast.error(error.message);
    toast.success("Third-party assurance recorded");
    router.refresh();
  }
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader><CardTitle>Assumptions Register</CardTitle></CardHeader>
        <CardContent className="grid gap-3 text-sm">
          {assumptions.length === 0 && <p className="text-muted-foreground">No assumptions recorded. They appear in the report&apos;s assumptions and limitations section.</p>}
          {assumptions.map((a) => (
            <div key={a.id} className="rounded-md border p-2">
              <span className="mr-2 rounded bg-muted px-1.5 py-0.5 text-xs capitalize">{a.category}</span>{a.statement}
              <div className="mt-1 text-xs text-muted-foreground">{a.profiles?.full_name ?? "—"} · {fmtDate(a.created_at)}</div>
            </div>
          ))}
          {canWrite && (
            <form onSubmit={add} className="grid gap-2 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
              <Field label="Category" htmlFor="as-cat"><NativeSelect id="as-cat" name="category">{["boundary", "methodology", "data", "estimate", "exclusion", "other"].map((c) => <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>)}</NativeSelect></Field>
              <Field label="Assumption" htmlFor="as-text"><Textarea id="as-text" name="statement" rows={1} required /></Field>
              <Button type="submit">Add</Button>
            </form>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Third-party assurance</CardTitle></CardHeader>
        <CardContent className="grid gap-3 text-sm">
          {verifications.length === 0 ? (
            <p className="text-muted-foreground">None recorded. Reports state that no third-party assurance has taken place.</p>
          ) : verifications.map((v) => (
            <p key={v.id}>{v.verifier} · {v.standard} · {v.assurance_level} assurance · {fmtDate(v.statement_date)} · {v.scope}</p>
          ))}
          {isInternal && (
            <form onSubmit={addVerification} className="grid gap-2 sm:grid-cols-3">
              <Field label="Assurance provider" htmlFor="vf-v"><Input id="vf-v" name="verifier" required /></Field>
              <Field label="Standard" htmlFor="vf-s"><Input id="vf-s" name="standard" placeholder="e.g. ISO 14064-3" required /></Field>
              <Field label="Level" htmlFor="vf-l"><NativeSelect id="vf-l" name="assurance_level"><option value="limited">Limited</option><option value="reasonable">Reasonable</option></NativeSelect></Field>
              <Field label="Statement date" htmlFor="vf-d"><Input id="vf-d" name="statement_date" type="date" required /></Field>
              <div className="sm:col-span-2"><Field label="Scope covered" htmlFor="vf-sc"><Input id="vf-sc" name="scope" required /></Field></div>
              <div><Button type="submit" variant="outline">Record assurance (internal)</Button></div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
