"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

export function NewOrganization({ categories, tiers }: {
  categories: { code: string; name: string; requires_crm_record: boolean }[];
  tiers: { code: string; name: string }[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("customer");
  const [busy, setBusy] = useState(false);
  const crmRequired = categories.find((c) => c.code === category)?.requires_crm_record ?? false;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const val = (k: string) => (String(f.get(k) ?? "").trim() || null);
    setBusy(true);
    try {
      const res = await engine<{ invitation_sent: boolean }>("/admin/organizations", {
        method: "POST",
        json: {
          legal_name: val("legal_name"), org_category: category, license_tier: val("license_tier"),
          sector_classification_code: val("sector_classification_code"), crm_record_id: val("crm_record_id"),
          tax_vat_number: val("tax_vat_number"), first_admin_email: val("first_admin_email"),
          first_admin_name: val("first_admin_name"),
        },
      });
      toast.success(res.invitation_sent ? "Organization created and invitation sent" : "Organization created");
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}><Plus /> New organization</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>New client organization</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="grid gap-4">
            <Field label="Organization name" htmlFor="o-name"><Input id="o-name" name="legal_name" required /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Category" htmlFor="o-cat">
                <NativeSelect id="o-cat" value={category} onChange={(e) => setCategory(e.target.value)}>
                  {categories.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                </NativeSelect>
              </Field>
              <Field label="License tier" htmlFor="o-tier" hint="Tier names and limits are pending the commercial model.">
                <NativeSelect id="o-tier" name="license_tier">
                  <option value="">—</option>
                  {tiers.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
                </NativeSelect>
              </Field>
              <Field label={`CRM record ID${crmRequired ? " (required)" : ""}`} htmlFor="o-crm">
                <Input id="o-crm" name="crm_record_id" required={crmRequired} />
              </Field>
              <Field label="Sector classification code" htmlFor="o-sector"><Input id="o-sector" name="sector_classification_code" /></Field>
              <Field label="Tax / VAT number" htmlFor="o-vat"><Input id="o-vat" name="tax_vat_number" /></Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="First Company Admin email" htmlFor="o-email"><Input id="o-email" name="first_admin_email" type="email" required /></Field>
              <Field label="First Company Admin name" htmlFor="o-admin"><Input id="o-admin" name="first_admin_name" /></Field>
            </div>
            <DialogFooter><Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create organization"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
