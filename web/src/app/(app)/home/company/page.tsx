import { PageHeader } from "@/components/app/page-header";
import { createClient } from "@/lib/supabase/server";
import { requireCompany } from "@/lib/session";
import { canManage } from "@/lib/permissions";
import { CompanyProfileForm } from "./company-profile-form";
import { FacilitiesPanel } from "./facilities-panel";

export default async function CompanyPage() {
  const ctx = await requireCompany();
  const supabase = await createClient();
  const ref = supabase.schema("ref");
  const [company, facilities, countries, currencies, sectors, sizes, facilityTypes, envClasses] = await Promise.all([
    supabase.from("companies").select("*").eq("id", ctx.activeCompany.id).single(),
    supabase.from("facilities").select("*").eq("company_id", ctx.activeCompany.id).order("is_company_level").order("name"),
    ref.from("countries").select("code, name").order("name"),
    ref.from("currencies").select("code, name").order("code"),
    ref.from("sectors").select("code, name, parent_code").order("sort"),
    ref.from("company_sizes").select("code, name").order("sort"),
    ref.from("facility_types").select("code, name").order("sort"),
    ref.from("environmental_classifications").select("code, name, status, source_name").order("sort"),
  ]);
  const lists = {
    countries: countries.data ?? [],
    currencies: currencies.data ?? [],
    sectors: sectors.data ?? [],
    sizes: sizes.data ?? [],
    facilityTypes: facilityTypes.data ?? [],
    envClasses: envClasses.data ?? [],
  };
  const editable = canManage(ctx);
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Home", href: "/home" }, { label: "Company & facilities" }]}
        title="Company & facilities"
        description="Set up the organisation and its facilities. Bangladesh is the default country, currency and timezone, but all three stay configurable."
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <CompanyProfileForm company={company.data} lists={lists} editable={editable} />
        <FacilitiesPanel companyId={ctx.activeCompany.id} facilities={facilities.data ?? []} lists={lists} editable={editable} />
      </div>
    </>
  );
}
