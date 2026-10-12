import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { RequirementsView, type Requirement } from "./requirements-view";

export default async function RegulationsPage() {
  const ctx = await requireCompany();
  const [reqs, metrics] = await Promise.all([
    engineGet<Requirement[]>(`/companies/${ctx.activeCompany.id}/requirements`),
    (await createClient()).schema("ref").from("metrics").select("key, name").order("sort"),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Governance" }, { label: "Regulatory requirements" }]} title="Regulatory requirements"
        description="Requirements that apply to the company and its facilities, decided by rules stored as data. Each shows its authority, source and effective date; uncertain items are marked NEEDS_REVIEW." />
      <RequirementsView requirements={reqs} canEdit={ctx.canEditLibrary} metrics={metrics.data ?? []} />
    </>
  );
}
