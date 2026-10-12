"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import type { Lists } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Company = Record<string, any> | null;

const EDITABLE = [
  "legal_name", "trading_name", "registration_number", "country_code", "address", "district", "city",
  "sector_code", "sub_sector_code", "company_size_code", "reporting_currency", "fiscal_year_start",
  "fiscal_year_end", "timezone",
] as const;

export function CompanyProfileForm({ company, lists, editable }: { company: Company; lists: Lists; editable: boolean }) {
  const router = useRouter();
  const [values, setValues] = useState(() => Object.fromEntries(EDITABLE.map((k) => [k, company?.[k] ?? ""])));
  const [saving, setSaving] = useState(false);
  if (!company) return null;
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setValues((v) => ({ ...v, [k]: e.target.value }));
  const topSectors = lists.sectors.filter((s) => !s.parent_code);
  const subSectors = lists.sectors.filter((s) => s.parent_code === values.sector_code);

  async function save() {
    if (!String(values.legal_name).trim()) return toast.error("Legal name is required");
    setSaving(true);
    const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v === "" ? null : v]));
    const { error } = await createClient().from("companies").update(payload).eq("id", company!.id);
    setSaving(false);
    if (error) return toast.error(error.message);
    toast.success("Company saved");
    router.refresh();
  }

  const text = (k: (typeof EDITABLE)[number], label: string, placeholder?: string) => (
    <Field label={label} htmlFor={k}>
      <Input id={k} value={values[k]} onChange={set(k)} disabled={!editable} placeholder={placeholder} />
    </Field>
  );
  const select = (k: (typeof EDITABLE)[number], label: string, options: { code: string; name: string }[], allowEmpty = true) => (
    <Field label={label} htmlFor={k}>
      <NativeSelect id={k} value={values[k]} onChange={set(k)} disabled={!editable}>
        {allowEmpty && <option value="">—</option>}
        {options.map((o) => (
          <option key={o.code} value={o.code}>{o.name}</option>
        ))}
      </NativeSelect>
    </Field>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Company profile</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {text("legal_name", "Legal name")}
          {text("trading_name", "Trading name")}
          {text("registration_number", "Registration no.")}
          {select("country_code", "Country", lists.countries, false)}
          {text("address", "Address")}
          {text("district", "District")}
          {text("city", "City")}
          {select("company_size_code", "Company size", lists.sizes)}
          {select("sector_code", "Sector", topSectors)}
          {select("sub_sector_code", "Sub-sector", subSectors)}
          {select("reporting_currency", "Reporting currency", lists.currencies.map((c) => ({ code: c.code, name: `${c.code} — ${c.name}` })), false)}
          {text("timezone", "Timezone", "Asia/Dhaka")}
          {text("fiscal_year_start", "Fiscal year start (MM-DD)", "07-01")}
          {text("fiscal_year_end", "Fiscal year end (MM-DD)", "06-30")}
        </div>
        {editable ? (
          <div>
            <Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save company"}</Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Your role can view but not edit the company profile.</p>
        )}
      </CardContent>
    </Card>
  );
}
