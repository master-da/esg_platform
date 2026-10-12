import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/server";
import { requireCompany } from "@/lib/session";
import { canAdminUsers } from "@/lib/permissions";
import { CompanyUsers } from "./company-users";
import { InternalUsers } from "./internal-users";

export default async function UsersPage() {
  const ctx = await requireCompany();
  const supabase = await createClient();
  const [members, internal] = await Promise.all([
    supabase
      .from("memberships")
      .select("id, role, status, user_id, profiles(full_name, email)")
      .eq("company_id", ctx.activeCompany.id)
      .order("created_at"),
    ctx.isInternal
      ? supabase.from("internal_users").select("user_id, internal_role, can_edit_library, active, profiles(full_name, email)")
      : Promise.resolve({ data: [] }),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Settings" }, { label: "Users & roles" }]}
        title="Users & roles"
        description="Company admins invite users and assign roles within their own company only."
      />
      <div className="grid gap-6">
        <CompanyUsers
          companyId={ctx.activeCompany.id}
          rows={(members.data ?? []) as never}
          canAdmin={canAdminUsers(ctx)}
          currentUserId={ctx.userId}
        />
        <div className="grid gap-6 lg:grid-cols-2">
          {ctx.isInternal ? (
            <InternalUsers rows={(internal.data ?? []) as never} isPlatformAdmin={ctx.internalRole === "PLATFORM_ADMIN"} />
          ) : (
            <Card>
              <CardHeader><CardTitle>Internal users (platform staff)</CardTitle></CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Platform admins can see all companies and projects and act as reviewers. They are not listed to client users.
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>Role rules</CardTitle></CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                <li>Company admins manage users; company admins and sustainability managers can approve or lock a project.</li>
                <li>Facility managers and data entry users can upload and categorize data, but cannot approve or lock.</li>
                <li>Viewers and auditors are read-only in every module.</li>
                <li>Users of one company can never see another company&apos;s data.</li>
                <li>The audit log is visible only to internal (platform) users.</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
