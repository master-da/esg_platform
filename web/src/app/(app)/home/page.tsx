import Link from "next/link";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { requireCompany } from "@/lib/session";

export default async function HomePage() {
  const ctx = await requireCompany();
  return (
    <>
      <PageHeader title={`Welcome${ctx.fullName ? `, ${ctx.fullName}` : ""}`} description={ctx.activeCompany.legal_name} />
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Company & facilities</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Keep the company profile and facility list up to date. <Link className="text-primary hover:underline" href="/home/company">Open →</Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Users & roles</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Invite colleagues and assign roles. <Link className="text-primary hover:underline" href="/settings/users">Open →</Link>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
