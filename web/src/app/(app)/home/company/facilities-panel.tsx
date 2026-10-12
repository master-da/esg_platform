"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";
import { cn } from "@/lib/utils";
import type { Lists } from "./types";

type Facility = {
  id: string;
  name: string;
  facility_type: string | null;
  address: string | null;
  district: string | null;
  city: string | null;
  operational_status: string;
  environmental_classification: string | null;
  employee_count: number | null;
  production_type: string | null;
  production_unit: string | null;
  production_quantity: number | null;
  is_company_level: boolean;
};

const BLANK: Omit<Facility, "id" | "is_company_level"> = {
  name: "", facility_type: "MANUFACTURING", address: "", district: "", city: "", operational_status: "operating",
  environmental_classification: "", employee_count: null, production_type: "", production_unit: "", production_quantity: null,
};

export function FacilitiesPanel({ companyId, facilities, lists, editable }: {
  companyId: string; facilities: Facility[]; lists: Lists; editable: boolean;
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | "new" | null>(facilities.find((f) => !f.is_company_level)?.id ?? null);
  const selected = selectedId === "new" ? null : facilities.find((f) => f.id === selectedId) ?? null;
  const typeName = (code: string | null) => lists.facilityTypes.find((t) => t.code === code)?.name ?? "—";

  return (
    <div className="grid content-start gap-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Facilities</CardTitle>
          {editable && (
            <Button size="sm" variant="outline" onClick={() => setSelectedId("new")}>
              <Plus /> Add facility
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>District</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {facilities.map((f) => (
                <TableRow
                  key={f.id}
                  onClick={() => setSelectedId(f.id)}
                  className={cn("cursor-pointer", selectedId === f.id && "bg-accent")}
                >
                  <TableCell className="font-medium">
                    {f.name}
                    {f.is_company_level && (
                      <div className="text-xs font-normal text-muted-foreground">Holds company-wide data such as travel and spend</div>
                    )}
                  </TableCell>
                  <TableCell>{f.is_company_level ? "—" : typeName(f.facility_type)}</TableCell>
                  <TableCell>{f.district ?? "—"}</TableCell>
                  <TableCell><StatusBadge status={f.operational_status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {(selected || selectedId === "new") && (
        <FacilityEditor
          key={selectedId}
          companyId={companyId}
          facility={selected}
          lists={lists}
          editable={editable && !selected?.is_company_level}
          onSaved={(id) => { setSelectedId(id); router.refresh(); }}
        />
      )}
    </div>
  );
}

function FacilityEditor({ companyId, facility, lists, editable, onSaved }: {
  companyId: string; facility: Facility | null; lists: Lists; editable: boolean; onSaved: (id: string) => void;
}) {
  const [v, setV] = useState(() => ({ ...BLANK, ...(facility ?? {}) }));
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof BLANK) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setV((s) => ({ ...s, [k]: e.target.value }));

  async function save() {
    if (!String(v.name).trim()) return toast.error("Facility name is required");
    const emp = v.employee_count === null || String(v.employee_count) === "" ? null : Number(v.employee_count);
    const qty = v.production_quantity === null || String(v.production_quantity) === "" ? null : Number(v.production_quantity);
    if ((emp !== null && (!Number.isInteger(emp) || emp < 0)) || (qty !== null && (!Number.isFinite(qty) || qty < 0)))
      return toast.error("Employee count and production quantity must be non-negative numbers");
    const payload = {
      name: v.name, facility_type: v.facility_type || null, address: v.address || null, district: v.district || null,
      city: v.city || null, operational_status: v.operational_status,
      environmental_classification: v.environmental_classification || null, employee_count: emp,
      production_type: v.production_type || null, production_unit: v.production_unit || null, production_quantity: qty,
    };
    setSaving(true);
    const supabase = createClient();
    const res = facility
      ? await supabase.from("facilities").update(payload).eq("id", facility.id).select("id").single()
      : await supabase.from("facilities").insert({ ...payload, company_id: companyId }).select("id").single();
    setSaving(false);
    if (res.error) return toast.error(res.error.message);
    toast.success(facility ? "Facility saved" : "Facility added");
    onSaved(res.data.id);
  }

  const text = (k: keyof typeof BLANK, label: string, type = "text") => (
    <Field label={label} htmlFor={`f-${k}`}>
      <Input id={`f-${k}`} type={type} value={String(v[k] ?? "")} onChange={set(k)} disabled={!editable} />
    </Field>
  );
  const envClass = lists.envClasses.find((c) => c.code === v.environmental_classification);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{facility ? `Facility details (${facility.name})` : "New facility"}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {text("name", "Name")}
          <Field label="Facility type" htmlFor="f-type">
            <NativeSelect id="f-type" value={v.facility_type ?? ""} onChange={set("facility_type")} disabled={!editable}>
              {lists.facilityTypes.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
            </NativeSelect>
          </Field>
          {text("address", "Address")}
          {text("district", "District")}
          {text("city", "City")}
          <Field label="Operational status" htmlFor="f-status">
            <NativeSelect id="f-status" value={v.operational_status} onChange={set("operational_status")} disabled={!editable}>
              <option value="operating">Operating</option>
              <option value="under_construction">Under construction</option>
              <option value="idle">Idle</option>
              <option value="closed">Closed</option>
            </NativeSelect>
          </Field>
          <Field
            label="Environmental classification"
            htmlFor="f-env"
            hint={envClass ? `${envClass.source_name ?? ""}${envClass.status === "NEEDS_REVIEW" ? " · pending domain-advisor review" : ""}` : undefined}
          >
            <NativeSelect id="f-env" value={v.environmental_classification ?? ""} onChange={set("environmental_classification")} disabled={!editable}>
              <option value="">—</option>
              {lists.envClasses.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
            </NativeSelect>
          </Field>
          {text("employee_count", "Employee count", "number")}
          {text("production_type", "Production type")}
          {text("production_unit", "Production unit")}
          {text("production_quantity", "Production quantity", "number")}
        </div>
        {editable && (
          <div>
            <Button onClick={save} disabled={saving}>{saving ? "Saving…" : facility ? "Save facility" : "Add facility"}</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
