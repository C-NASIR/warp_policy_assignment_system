import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { ButtonLink } from "@/components/ui";

export function SignupForm() {
  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="signup-title">
        <Link href="/" className="auth-brand" aria-label="PolicyOS home">
          <span className="brand-mark">P</span>
          <span>
            <strong>PolicyOS</strong>
            <small>Assignment engine</small>
          </span>
        </Link>
        <div className="auth-icon">
          <ShieldCheck size={21} />
        </div>
        <p className="eyebrow">Join your workspace</p>
        <h1 id="signup-title">Get access to PolicyOS</h1>
        <p className="page-subtitle">
          Ask your PolicyOS administrator to create an account for you, then sign in with the
          credentials they provide.
        </p>
        <ButtonLink className="auth-submit" href="/login" fullWidth>
          Sign in
        </ButtonLink>
        <Link className="auth-switch" href="/">
          Back to home
        </Link>
      </section>
    </main>
  );
}
