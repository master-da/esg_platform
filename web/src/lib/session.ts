import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Ctx, ExternalRole } from "@/lib/permissions";

export const ACTIVE_COMPANY_COOKIE = "active_company";

type RawContext = {
  user_id: string | null;
  email: string | null;
  full_name: string | null;
  internal_role: "PLATFORM_ADMIN" | "INTERNAL_USER" | null;
  can_edit_library: boolean;
  memberships: { company_id: string; company_name: string; role: ExternalRole; status: string }[];
};

/** The signed-in user's context and active company. Cached for the duration of one request. */
export const getContext = cache(async (): Promise<Ctx> => {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("my_context");
  const raw = data as RawContext | null;
  if (error || !raw?.user_id) redirect("/login");

  const isInternal = raw.internal_role !== null;
  const active = raw.memberships.filter((m) => m.status === "active");
  let companies: { id: string; legal_name: string }[];
  if (isInternal) {
    const { data: rows } = await supabase.from("companies").select("id, legal_name").order("legal_name");
    companies = rows ?? [];
  } else {
    companies = active.map((m) => ({ id: m.company_id, legal_name: m.company_name }));
  }

  const wanted = (await cookies()).get(ACTIVE_COMPANY_COOKIE)?.value;
  const activeCompany = companies.find((c) => c.id === wanted) ?? companies[0] ?? null;
  const role = activeCompany ? (active.find((m) => m.company_id === activeCompany.id)?.role ?? null) : null;

  return {
    userId: raw.user_id,
    email: raw.email ?? "",
    fullName: raw.full_name,
    internalRole: raw.internal_role,
    isInternal,
    canEditLibrary: raw.can_edit_library,
    companies,
    activeCompany,
    role,
  };
});

/** For pages that need a company: returns the context with a non-null active company. */
export async function requireCompany(): Promise<Ctx & { activeCompany: { id: string; legal_name: string } }> {
  const ctx = await getContext();
  if (!ctx.activeCompany) redirect("/no-company");
  return ctx as Ctx & { activeCompany: { id: string; legal_name: string } };
}

export async function requireInternal(): Promise<Ctx> {
  const ctx = await getContext();
  if (!ctx.isInternal) redirect("/home");
  return ctx;
}
