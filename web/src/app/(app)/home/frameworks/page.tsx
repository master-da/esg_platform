import { PageHeader } from "@/components/app/page-header";
import { requireCompany } from "@/lib/session";
import { canManage } from "@/lib/permissions";
import { createClient } from "@/lib/supabase/server";
import { FrameworkList } from "./framework-list";

export default async function FrameworksPage() {
  const ctx = await requireCompany();
  const supabase = await createClient();
  const ref = supabase.schema("ref");
  const [frameworks, mappings, metrics, selected] = await Promise.all([
    ref.from("frameworks").select("*").order("sort"),
    ref.from("framework_metric_mappings").select("*").order("sort"),
    ref.from("metrics").select("key, name, unit, module, description").order("sort"),
    supabase.from("company_frameworks").select("framework_key").eq("company_id", ctx.activeCompany.id),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Home" }, { label: "Reporting frameworks" }]} title="Reporting frameworks"
        description="Choose the frameworks you report against. Each maps disclosures to the same metric library, so numbers are calculated once." />
      <FrameworkList companyId={ctx.activeCompany.id} frameworks={frameworks.data ?? []} mappings={mappings.data ?? []}
        metrics={metrics.data ?? []} selected={(selected.data ?? []).map((s) => s.framework_key)} canEdit={canManage(ctx)} />
    </>
  );
}
