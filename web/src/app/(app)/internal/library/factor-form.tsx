"use client";

import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

export function FactorForm({ nodeId, units, geographies, onSaved }: {
  nodeId: string; units: { code: string; name: string }[]; geographies: { code: string; name: string }[];
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => (String(f.get(k) ?? "").trim() || null);
    setBusy(true);
    try {
      await engine("/library/factors", {
        method: "POST",
        json: {
          taxonomy_node_id: nodeId, geography_code: v("geography_code"), activity_unit: v("activity_unit"),
          co2e: v("co2e"), co2e_co2: v("co2e_co2"), co2e_ch4: v("co2e_ch4"), co2e_n2o: v("co2e_n2o"),
          gwp_version: v("gwp_version"), source_name: v("source_name"), source_url: v("source_url"),
          source_year: v("source_year"), source_ref: v("source_ref"), methodology: v("methodology"),
          quality_rating: v("quality_rating"), valid_from: v("valid_from"), valid_to: v("valid_to"), notes: v("notes"),
        },
      });
      toast.success("Draft factor saved. Review it, then activate.");
      onSaved();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-4 rounded-lg border bg-muted/30 p-4">
      <p className="text-sm text-muted-foreground">
        Every factor must trace to a real, citable source. A new factor is saved as a draft and is not used until activated.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Geography" htmlFor="ff-geo">
          <NativeSelect id="ff-geo" name="geography_code" defaultValue="BD" required>
            {geographies.map((g) => <option key={g.code} value={g.code}>{g.code} — {g.name}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Activity unit (per …)" htmlFor="ff-unit">
          <NativeSelect id="ff-unit" name="activity_unit" required>
            {units.map((u) => <option key={u.code} value={u.code}>{u.name}</option>)}
          </NativeSelect>
        </Field>
        <Field label="kg CO₂e per unit" htmlFor="ff-co2e"><Input id="ff-co2e" name="co2e" inputMode="decimal" required /></Field>
        <Field label="of which CO₂" htmlFor="ff-co2"><Input id="ff-co2" name="co2e_co2" inputMode="decimal" /></Field>
        <Field label="of which CH₄ (as CO₂e)" htmlFor="ff-ch4"><Input id="ff-ch4" name="co2e_ch4" inputMode="decimal" /></Field>
        <Field label="of which N₂O (as CO₂e)" htmlFor="ff-n2o"><Input id="ff-n2o" name="co2e_n2o" inputMode="decimal" /></Field>
        <Field label="GWP version" htmlFor="ff-gwp"><Input id="ff-gwp" name="gwp_version" defaultValue="AR5" required /></Field>
        <Field label="Valid from" htmlFor="ff-from"><Input id="ff-from" name="valid_from" type="date" required /></Field>
        <Field label="Valid to" htmlFor="ff-to"><Input id="ff-to" name="valid_to" type="date" required /></Field>
        <Field label="Source name" htmlFor="ff-src"><Input id="ff-src" name="source_name" required /></Field>
        <Field label="Source URL" htmlFor="ff-url"><Input id="ff-url" name="source_url" type="url" /></Field>
        <Field label="Source year" htmlFor="ff-year"><Input id="ff-year" name="source_year" type="number" required /></Field>
        <Field label="Source reference (table / row)" htmlFor="ff-ref"><Input id="ff-ref" name="source_ref" /></Field>
        <Field label="Methodology" htmlFor="ff-meth"><Input id="ff-meth" name="methodology" /></Field>
        <Field label="Quality rating" htmlFor="ff-q"><Input id="ff-q" name="quality_rating" /></Field>
      </div>
      <Field label="Notes" htmlFor="ff-notes"><Textarea id="ff-notes" name="notes" rows={2} /></Field>
      <div><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save draft factor"}</Button></div>
    </form>
  );
}
