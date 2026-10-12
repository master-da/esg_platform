import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <AuthCard title="Sign in" subtitle="Use the email address your administrator invited.">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
