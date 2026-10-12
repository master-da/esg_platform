export type Option = { code: string; name: string };
export type Lists = {
  countries: Option[];
  currencies: Option[];
  sectors: (Option & { parent_code: string | null })[];
  sizes: Option[];
  facilityTypes: Option[];
  envClasses: (Option & { status: string; source_name: string | null })[];
};
