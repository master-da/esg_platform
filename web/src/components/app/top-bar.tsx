"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { LogOut } from "lucide-react";
import { setActiveCompany } from "@/app/actions";
import { createClient } from "@/lib/supabase/client";
import { NativeSelect } from "@/components/app/native-select";
import { Button } from "@/components/ui/button";
import { ROLE_LABELS, type Ctx } from "@/lib/permissions";

export function TopBar({ ctx }: { ctx: Ctx }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const roleLabel = ctx.internalRole
    ? ctx.internalRole === "PLATFORM_ADMIN" ? "Platform admin (internal)" : "Internal user"
    : ctx.role ? ROLE_LABELS[ctx.role] : "";

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b bg-background/95 px-6 backdrop-blur">
      <div className="flex items-center gap-2">
        {ctx.companies.length > 1 || ctx.isInternal ? (
          <NativeSelect
            aria-label="Active company"
            className="w-72"
            value={ctx.activeCompany?.id ?? ""}
            disabled={pending}
            onChange={(e) => start(() => setActiveCompany(e.target.value))}
          >
            {ctx.companies.length === 0 && <option value="">No companies yet</option>}
            {ctx.companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.legal_name}
              </option>
            ))}
          </NativeSelect>
        ) : (
          <span className="text-sm font-medium">{ctx.activeCompany?.legal_name}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right leading-tight">
          <div className="text-sm font-medium">{ctx.fullName ?? ctx.email}</div>
          <div className="text-xs text-muted-foreground">{roleLabel}</div>
        </div>
        <Button variant="ghost" size="icon" onClick={signOut} title="Sign out" aria-label="Sign out">
          <LogOut />
        </Button>
      </div>
    </header>
  );
}
