import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireInternal } from "@/lib/session";
import { createClient } from "@/lib/supabase/server";
import { LibraryBrowser, type TreeNode } from "./library-browser";

export default async function LibraryPage() {
  const ctx = await requireInternal();
  const supabase = await createClient();
  const [tree, units, geos] = await Promise.all([
    engineGet<TreeNode[]>("/library/tree"),
    supabase.schema("ref").from("units").select("code, name, dimension").order("sort"),
    supabase.schema("ref").from("geographies").select("code, name, level").order("code"),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Internal" }, { label: "Emission factor library" }]}
        title="Emission factor library"
        description="Internal tool. Factor codes, values, sources, validity and conversions. Every change is audited; active factors are immutable and corrected by a new version."
      />
      <LibraryBrowser
        tree={tree}
        canEdit={ctx.canEditLibrary}
        units={units.data ?? []}
        geographies={geos.data ?? []}
      />
    </>
  );
}
