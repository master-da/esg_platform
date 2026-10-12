"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";

export default function SetPasswordPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password"));
    if (password.length < 8) return setError("Use at least 8 characters.");
    if (password !== String(form.get("confirm"))) return setError("The passwords do not match.");
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password });
    if (error) return setError(error.message);
    await supabase.rpc("accept_invitations");
    router.push("/home");
    router.refresh();
  }

  return (
    <AuthCard title="Choose your password">
      <form onSubmit={onSubmit} className="grid gap-4">
        <Field label="New password" htmlFor="password">
          <Input id="password" name="password" type="password" autoComplete="new-password" required />
        </Field>
        <Field label="Confirm password" htmlFor="confirm">
          <Input id="confirm" name="confirm" type="password" autoComplete="new-password" required />
        </Field>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit">Save password</Button>
      </form>
    </AuthCard>
  );
}
