import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createClient } from "@/lib/supabase/server";
import { requireInternal } from "@/lib/session";
import { fmtDate } from "@/lib/format";
import { NewOrganization } from "./new-organization";

export default async function OrganizationsPage() {
  await requireInternal();
  const supabase = await createClient();
  const [orgs, categories, tiers] = await Promise.all([
    supabase.from("companies")
      .select("id, legal_name, org_category, license_tier, sector_classification_code, crm_record_id, tax_vat_number, created_at")
      .order("created_at", { ascending: false }),
    supabase.schema("ref").from("org_categories").select("code, name, requires_crm_record"),
    supabase.schema("ref").from("license_tiers").select("code, name"),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Settings" }, { label: "Organizations" }]}
        title="Organizations"
        description="Internal users create client organizations and invite each one's first Company Admin."
        actions={<NewOrganization categories={categories.data ?? []} tiers={tiers.data ?? []} />}
      />
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Organization</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>License tier</TableHead>
                <TableHead>Sector code</TableHead>
                <TableHead>CRM record</TableHead>
                <TableHead>Tax / VAT</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(orgs.data ?? []).map((o) => (
                <TableRow key={o.id}>
                  <TableCell className="font-medium">{o.legal_name}</TableCell>
                  <TableCell>{o.org_category}</TableCell>
                  <TableCell>{o.license_tier ?? "—"}</TableCell>
                  <TableCell>{o.sector_classification_code ?? "—"}</TableCell>
                  <TableCell>{o.crm_record_id ?? "—"}</TableCell>
                  <TableCell>{o.tax_vat_number ?? "—"}</TableCell>
                  <TableCell>{fmtDate(o.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
