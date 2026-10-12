"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { ACTIVE_COMPANY_COOKIE } from "@/lib/session";

export async function setActiveCompany(companyId: string) {
  (await cookies()).set(ACTIVE_COMPANY_COOKIE, companyId, { path: "/", sameSite: "lax", httpOnly: true });
  revalidatePath("/", "layout");
}
