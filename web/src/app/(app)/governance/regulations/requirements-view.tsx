"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

export type Requirement = {
  id: string; code: string; version: number; regulator: string; law: string; title: string; description: string | null;
  frequency: string | null; required_metric_key: string | null; required_document: string | null; source_url: string;
  effective_date: string; status: string; review_note: string | null; applies: boolean; level: string;
  applies_to: { facility: string; because: string[] }[];
};

const FIELDS = ["facility.environmental_classification", "facility.facility_type", "facility.employee_count", "facility.operational_status",
  "company.sector_code", "company.sub_sector_code", "company.company_size_code", "company.country_code"];
const OPS = ["in", "eq", "ne", "not_in", "gte", "gt", "lte", "lt"];

export function RequirementsView({ requirements, canEdit, metrics }: { requirements: Requirement[]; canEdit: boolean; metrics: { key: string; name: string }[] }) {
  const [showAll, setShowAll] = useState(false);
  const [adding, setAdding] = useState(false);
  const shown = requirements.filter((r) => showAll || r.applies).sort((a, b) => Number(b.applies) - Number(a.applies));
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Also show requirements that do not apply</label>
        {canEdit && <Button size="sm" variant="outline" onClick={() => setAdding((a) => !a)}><Plus /> {adding ? "Cancel" : "Add requirement"}</Button>}
      </div>
      {adding && <RequirementForm metrics={metrics} onDone={() => setAdding(false)} />}
      {shown.length === 0 && <Card><CardContent className="py-6 text-sm text-muted-foreground">No configured requirement applies to this company. Requirements are added only from authoritative sources.</CardContent></Card>}
      {shown.map((r) => (
        <Card key={r.id} className={r.applies ? undefined : "opacity-70"}>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle>{r.title}</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">{r.regulator} · {r.law}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-1">
              <StatusBadge status={r.applies ? "applies" : "na"} label={r.applies ? "Applies" : "Does not apply"} tone={r.applies ? "blue" : "gray"} />
              <StatusBadge status={r.status} />
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm md:grid-cols-[2fr_1fr]">
            <div className="grid gap-2">
              {r.description && <p>{r.description}</p>}
              {r.applies && (
                <div>
                  <div className="text-xs font-medium text-muted-foreground">Applies to</div>
                  <ul className="text-sm">{r.applies_to.map((a) => <li key={a.facility}>{a.facility} <span className="text-xs text-muted-foreground">because {a.because.join(", ")}</span></li>)}</ul>
                </div>
              )}
              {r.review_note && <p className="text-xs text-amber-800">Review note: {r.review_note}</p>}
            </div>
            <dl className="grid grid-cols-[7rem_1fr] gap-x-2 gap-y-1 text-xs">
              <dt className="text-muted-foreground">Frequency</dt><dd>{r.frequency ?? "—"}</dd>
              <dt className="text-muted-foreground">Document</dt><dd>{r.required_document ?? "—"}</dd>
              <dt className="text-muted-foreground">Metric</dt><dd>{metrics.find((m) => m.key === r.required_metric_key)?.name ?? "—"}</dd>
              <dt className="text-muted-foreground">Effective</dt><dd>{fmtDate(r.effective_date)} · v{r.version}</dd>
              <dt className="text-muted-foreground">Source</dt><dd><a className="text-primary hover:underline" href={r.source_url} target="_blank" rel="noreferrer">Official text / reference</a></dd>
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RequirementForm({ metrics, onDone }: { metrics: { key: string; name: string }[]; onDone: () => void }) {
  const router = useRouter();
  const [conds, setConds] = useState([{ field: FIELDS[0], op: "in", value: "" }]);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "").trim() || null;
    const parsed = conds.filter((c) => c.value.trim()).map((c) => ({
      field: c.field, op: c.op,
      value: c.op === "in" || c.op === "not_in" ? c.value.split(",").map((x) => x.trim()).filter(Boolean)
        : /^-?\d+(\.\d+)?$/.test(c.value.trim()) ? Number(c.value) : c.value.trim(),
    }));
    try {
      await engine("/reference/requirements", { method: "POST", json: {
        code: v("code"), regulator: v("regulator"), law: v("law"), title: v("title"), description: v("description"),
        frequency: v("frequency"), required_document: v("required_document"), required_metric_key: v("required_metric_key"),
        source_url: v("source_url"), effective_date: v("effective_date"), status: v("status"), review_note: v("review_note"),
        applies_universally: f.get("universal") === "on", applicability_conditions: { all: parsed },
      } });
      toast.success("Requirement saved (a new version if the code exists)");
      onDone();
      router.refresh();
    } catch (err) { toast.error((err as Error).message); }
  }
  return (
    <Card>
      <CardHeader><CardTitle>New requirement or new version</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <Field label="Code (reuse a code to create a new version)" htmlFor="rq-code"><Input id="rq-code" name="code" required /></Field>
          <Field label="Regulator" htmlFor="rq-reg"><Input id="rq-reg" name="regulator" required /></Field>
          <Field label="Law / rule" htmlFor="rq-law"><Input id="rq-law" name="law" required /></Field>
          <Field label="Requirement" htmlFor="rq-title"><Input id="rq-title" name="title" required /></Field>
          <div className="sm:col-span-2"><Field label="Description" htmlFor="rq-desc"><Textarea id="rq-desc" name="description" rows={2} /></Field></div>
          <Field label="Frequency" htmlFor="rq-freq"><Input id="rq-freq" name="frequency" /></Field>
          <Field label="Required document" htmlFor="rq-doc"><Input id="rq-doc" name="required_document" /></Field>
          <Field label="Required metric" htmlFor="rq-metric"><NativeSelect id="rq-metric" name="required_metric_key"><option value="">—</option>{metrics.map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}</NativeSelect></Field>
          <Field label="Source URL (authoritative)" htmlFor="rq-url"><Input id="rq-url" name="source_url" type="url" required /></Field>
          <Field label="Effective date" htmlFor="rq-eff"><Input id="rq-eff" name="effective_date" type="date" required /></Field>
          <Field label="Status" htmlFor="rq-status"><NativeSelect id="rq-status" name="status"><option value="NEEDS_REVIEW">NEEDS_REVIEW</option><option value="VERIFIED">VERIFIED</option></NativeSelect></Field>
          <div className="sm:col-span-2"><Field label="Review note" htmlFor="rq-note"><Input id="rq-note" name="review_note" /></Field></div>
          <div className="grid gap-2 sm:col-span-2">
            <div className="text-xs font-medium text-muted-foreground">Applies when ALL of these hold (values for in / not in: comma-separated)</div>
            {conds.map((c, i) => (
              <div key={i} className="flex gap-2">
                <NativeSelect value={c.field} onChange={(e) => setConds((cs) => cs.map((x, j) => (j === i ? { ...x, field: e.target.value } : x)))}>{FIELDS.map((fl) => <option key={fl}>{fl}</option>)}</NativeSelect>
                <NativeSelect className="w-28" value={c.op} onChange={(e) => setConds((cs) => cs.map((x, j) => (j === i ? { ...x, op: e.target.value } : x)))}>{OPS.map((o) => <option key={o}>{o}</option>)}</NativeSelect>
                <Input value={c.value} placeholder="e.g. ORANGE, RED  or  50" onChange={(e) => setConds((cs) => cs.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
                <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove condition" onClick={() => setConds((cs) => cs.filter((_, j) => j !== i))}><Trash2 /></Button>
              </div>
            ))}
            <div className="flex items-center gap-4">
              <Button type="button" size="sm" variant="outline" onClick={() => setConds((cs) => [...cs, { field: FIELDS[0], op: "in", value: "" }])}>Add condition</Button>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="universal" /> Genuinely applies to every company</label>
            </div>
          </div>
          <div><Button type="submit">Save requirement</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}
