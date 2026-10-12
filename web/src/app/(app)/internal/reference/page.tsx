import { PageHeader } from "@/components/app/page-header";
import { requireInternal } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { ReferenceAdmin } from "./reference-admin";

export default async function ReferencePage() {
  const ctx = await requireInternal();
  const ref = (await createClient()).schema("ref");
  const [metrics, frameworks, mappings] = await Promise.all([
    ref.from("metrics").select("*").order("sort"),
    ref.from("frameworks").select("*").order("sort"),
    ref.from("framework_metric_mappings").select("*").order("framework_key").order("sort"),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ label: "Internal" }, { label: "Reference data" }]} title="Reference data"
        description="Metric parameters, frameworks and their metric mappings. Changes are data (audited), never code. Regulatory requirements are edited on the Governance page; water-quality limits on the Water page." />
      <ReferenceAdmin metrics={metrics.data ?? []} frameworks={frameworks.data ?? []} mappings={mappings.data ?? []} canEdit={ctx.canEditLibrary} />
    </>
  );
}
