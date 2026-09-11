import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { AuthForm } from "@/components/auth-form";
import { getCurrentUser, getRootSetupStatus } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";

export const metadata: Metadata = { title: "Sign up" };

export default async function SignupPage() {
  const user = await getCurrentUser();
  if (user) redirect(firstAllowedPath(user));
  const setup = await getRootSetupStatus();
  if (!setup.setup_required) {
    return (
      <main className="auth-page">
        <section className="auth-card" aria-labelledby="signup-title">
          <Link href="/" className="auth-brand">
            <span className="brand-mark">P</span>
            <strong>PolicyOS</strong>
          </Link>
          <div className="auth-icon">
            <ShieldCheck size={21} />
          </div>
          <p className="eyebrow">Join your workspace</p>
          <h1 id="signup-title">Get access to PolicyOS</h1>
          <p className="page-subtitle">
            This workspace is already set up. Ask your PolicyOS administrator to create an account
            for you, then sign in with the credentials they provide.
          </p>
          <Link className="button auth-submit" href="/login">
            Sign in
          </Link>
          <Link className="auth-switch" href="/">
            Back to home
          </Link>
        </section>
      </main>
    );
  }
  return <AuthForm mode="setup" />;
}
