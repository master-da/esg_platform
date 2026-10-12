import { PageHeader } from "@/components/app/page-header";
import { engineGet } from "@/lib/engine-server";
import { requireCompany } from "@/lib/session";
import { canWrite } from "@/lib/permissions";
import { BillReview, type BillData } from "./bill-review";

export default async function BillPage(props: PageProps<"/environmental/projects/[projectId]/[terminal]/bills/[fileId]">) {
  const { projectId, terminal, fileId } = await props.params;
  const ctx = await requireCompany();
  const bill = await engineGet<BillData>(`/files/${fileId}/bill`);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Environmental" }, { label: "Projects", href: "/environmental/projects" }, { label: "Project", href: `/environmental/projects/${projectId}` },
          { label: "Purchased electricity", href: `/environmental/projects/${projectId}/${terminal}` }, { label: "Bill" }]}
        title="Purchased electricity"
        description="Bill photo or PDF: the AI proposes values, you confirm them."
      />
      <BillReview bill={bill} backHref={`/environmental/projects/${projectId}/${terminal}`} canWrite={canWrite(ctx)} />
    </>
  );
}
