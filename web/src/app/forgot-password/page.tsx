"use client";

import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    const { error } = await createClient().auth.resetPasswordForEmail(email);
    if (error) setError(error.message);
    else setSent(true);
  }

  return (
    <AuthCard title="Reset password" subtitle="We'll email you a link to choose a new password.">
      {sent ? (
        <p className="text-sm">If an account exists for that address, a reset link is on its way.</p>
      ) : (
        <form onSubmit={onSubmit} className="grid gap-4">
          <Field label="Email" htmlFor="email">
            <Input id="email" name="email" type="email" required />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit">Send reset link</Button>
        </form>
      )}
      <Link href="/login" className="mt-4 block text-center text-sm text-muted-foreground hover:underline">
        Back to sign in
      </Link>
    </AuthCard>
  );
}
