import { PageHeader } from "@/components/app/page-header";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { PermitsView } from "./permits-view";

export default async function PermitsPage() {
  const ctx = await requireCompany();
  const supabase = await createClient();
  const [permits, facilities] = await Promise.all([
    supabase.from("permits").select("*, facilities(name)").eq("company_id", ctx.activeCompany.id).order("expiry_date", { ascending: true, nullsFirst: false }),
    supabase.from("facilities").select("id, name").eq("company_id", ctx.activeCompany.id).eq("is_company_level", false).order("name"),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Governance" }, { label: "Permits & licences" }]} title="Permits & licences"
        description="Permits, licences and certificates with renewal reminders ahead of expiry, using each permit's own lead time." />
      <PermitsView companyId={ctx.activeCompany.id} permits={(permits.data ?? []) as never} facilities={facilities.data ?? []} canWrite={canWrite(ctx)} />
    </>
  );
}
