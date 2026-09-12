"use client";

import { ArrowRight, CircleAlert, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type SubmitEvent, useState } from "react";
import { Button, FormField, TextInput } from "@/components/ui";
import { firstAllowedPath } from "@/lib/permissions";
import type { CurrentUser } from "@/lib/types";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [factor, setFactor] = useState("");
  const [factorRequired, setFactorRequired] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/backend/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          ...(factorRequired
            ? useRecovery
              ? { recovery_code: factor }
              : { mfa_code: factor }
            : {}),
        }),
      });
      const result = (await response.json().catch(() => ({}))) as Partial<CurrentUser> & {
        error?: { code?: string; issues?: { message?: string }[]; message?: string };
        detail?: string;
      };
      if (!response.ok) {
        if (result.error?.code === "mfa_required") {
          setFactorRequired(true);
          setError("");
          return;
        }
        throw new Error(
          result.error?.issues?.[0]?.message ??
            result.error?.message ??
            result.detail ??
            "Authentication could not be completed.",
        );
      }
      router.replace(firstAllowedPath(result as CurrentUser));
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <Link href="/" className="auth-brand" aria-label="PolicyOS home">
          <span className="brand-mark">P</span>
          <span>
            <strong>PolicyOS</strong>
            <small>Assignment engine</small>
          </span>
        </Link>
        <p className="eyebrow">Welcome back</p>
        <h1 id="login-title">Sign in to PolicyOS</h1>
        <p className="page-subtitle">Use the account created for this PolicyOS workspace.</p>
        {error && (
          <div className="error-banner auth-message" role="alert">
            <CircleAlert size={14} />
            {error}
          </div>
        )}
        <form className="auth-form" onSubmit={submit}>
          <FormField label="Email address" htmlFor="login-email" required>
            <TextInput
              id="login-email"
              required
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
            />
          </FormField>
          <FormField label="Password" htmlFor="login-password" required>
            <TextInput
              id="login-password"
              required
              type="password"
              maxLength={128}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>
          {factorRequired && (
            <>
              <FormField
                label={useRecovery ? "Recovery code" : "Authenticator code"}
                htmlFor="login-factor"
                required
              >
                <TextInput
                  id="login-factor"
                  required
                  inputMode={useRecovery ? "text" : "numeric"}
                  autoComplete="one-time-code"
                  value={factor}
                  onChange={(event) => setFactor(event.target.value)}
                  placeholder={useRecovery ? "xxxxxx-xxxxxx" : "000000"}
                />
              </FormField>
              <Button
                variant="secondary"
                type="button"
                onClick={() => {
                  setUseRecovery((value) => !value);
                  setFactor("");
                }}
              >
                {useRecovery ? "Use authenticator code" : "Use a recovery code"}
              </Button>
            </>
          )}
          <Button className="auth-submit" disabled={busy} type="submit" fullWidth>
            {busy ? "Please wait…" : "Sign in"}
            <ArrowRight size={14} />
          </Button>
        </form>
        <Link className="popover-footer" href="/recover">
          Forgot your password?
        </Link>
        <p className="auth-switch">
          New to PolicyOS? <Link href="/signup">Sign up</Link>
        </p>
        <div className="auth-security">
          <LockKeyhole size={13} />
          <span>Your session is stored in a secure, HTTP-only cookie.</span>
        </div>
      </section>
    </main>
  );
}
