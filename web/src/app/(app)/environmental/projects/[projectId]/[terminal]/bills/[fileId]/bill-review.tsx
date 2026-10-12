"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

export type BillData = {
  file: { id: string; name: string; content_type: string };
  preview_url: string;
  fields: { key: string; label: string }[];
  facilities: { id: string; name: string }[];
  units: string[];
  extraction: {
    status: "AI_EXTRACTED" | "USER_VERIFIED" | "FAILED"; provider: string; model: string | null; error: string | null;
    extracted: { fields: Record<string, string | null>; confidence: Record<string, string> } | null;
    confirmed: Record<string, string> | null;
  };
};

const CONF: Record<string, string> = { high: "text-emerald-700", medium: "text-amber-700", low: "text-red-700" };

/** Wireframe "AI Document Extraction review": editable values; nothing is saved until confirmed. */
export function BillReview({ bill, backHref, canWrite }: { bill: BillData; backHref: string; canWrite: boolean }) {
  const router = useRouter();
  const ex = bill.extraction;
  const proposed = ex.confirmed ?? ex.extracted?.fields ?? {};
  const [values, setValues] = useState<Record<string, string>>(() => ({
    ...Object.fromEntries(bill.fields.map((f) => [f.key, String(proposed[f.key] ?? "")])),
    facility_id: String(proposed.facility_id ?? bill.facilities.find((f) => !f.name.startsWith("Company-level"))?.id ?? bill.facilities[0]?.id ?? ""),
    unit: String(proposed.unit ?? "kWh"),
  }));
  const [busy, setBusy] = useState(false);
  const done = ex.status === "USER_VERIFIED";

  async function confirm() {
    setBusy(true);
    try {
      await engine(`/files/${bill.file.id}/bill/confirm`, {
        method: "POST",
        json: {
          facility_id: values.facility_id, period_start: values.period_start, period_end: values.period_end,
          supplier_name: values.supplier_name, meter_id: values.meter_id || null, quantity: values.quantity,
          unit: values.unit, amount_billed: values.amount_billed || null,
        },
      });
      toast.success("Confirmed. The row now waits for categorization like any other.");
      router.push(backHref);
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message, { duration: 10000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Uploaded bill</CardTitle></CardHeader>
        <CardContent>
          {bill.file.content_type === "application/pdf" ? (
            <iframe src={bill.preview_url} title="Bill preview" className="h-[70vh] w-full rounded-md border" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={bill.preview_url} alt="Bill preview" className="max-h-[70vh] w-full rounded-md border object-contain" />
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <CardTitle>Extracted fields</CardTitle>
          <StatusBadge status={ex.status === "FAILED" ? "NEEDS" : ex.status} label={ex.status === "FAILED" ? "Manual entry" : ex.status} />
        </CardHeader>
        <CardContent className="grid gap-4">
          {ex.error && <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">{ex.error}</p>}
          <Table>
            <TableHeader><TableRow><TableHead>Field</TableHead><TableHead>Value (editable)</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>Facility</TableCell>
                <TableCell>
                  <NativeSelect value={values.facility_id} disabled={done} onChange={(e) => setValues((v) => ({ ...v, facility_id: e.target.value }))}>
                    {bill.facilities.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </NativeSelect>
                </TableCell>
              </TableRow>
              {bill.fields.map(({ key, label }) => (
                <TableRow key={key}>
                  <TableCell>
                    {label}
                    {ex.extracted?.confidence?.[key] && <div className={`text-xs ${CONF[ex.extracted.confidence[key]]}`}>{ex.extracted.confidence[key]} confidence</div>}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Input
                        type={key.startsWith("period") ? "date" : "text"}
                        inputMode={key === "quantity" || key === "amount_billed" ? "decimal" : undefined}
                        value={values[key] ?? ""}
                        disabled={done}
                        onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                      />
                      {key === "quantity" && (
                        <NativeSelect className="w-24" value={values.unit} disabled={done} onChange={(e) => setValues((v) => ({ ...v, unit: e.target.value }))}>
                          {bill.units.map((u) => <option key={u}>{u}</option>)}
                        </NativeSelect>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {done ? (
            <p className="text-sm text-emerald-800">Confirmed as USER_VERIFIED. <a className="underline" href={backHref}>Back to the category</a></p>
          ) : canWrite ? (
            <div className="flex items-center gap-2">
              <Button onClick={confirm} disabled={busy}>{busy ? "Saving…" : "Confirm → USER_VERIFIED"}</Button>
              <Button variant="outline" onClick={() => router.push(backHref)}>Back</Button>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Nothing is saved until you confirm. AI never sets the emissions number: it only reads the bill
            {ex.model ? ` (${ex.model})` : ""}; the calculation engine does the rest after categorization.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
