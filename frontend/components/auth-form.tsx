"use client";

import { ArrowRight, Check, CircleAlert, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { firstAllowedPath } from "@/lib/permissions";
import type { CurrentUser } from "@/lib/types";

type AuthMode = "login" | "setup";

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [factor, setFactor] = useState("");
  const [factorRequired, setFactorRequired] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isSetup = mode === "setup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSetup && password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/backend/auth/${isSetup ? "setup-root" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isSetup ? { name, email, password } : {
          email,
          password,
          ...(factorRequired ? useRecovery ? { recovery_code: factor } : { mfa_code: factor } : {}),
        }),
      });
      const result = await response.json().catch(() => ({})) as Partial<CurrentUser> & { error?: { code?: string; issues?: { message?: string }[]; message?: string }; detail?: string };
      if (!response.ok) {
        if (result.error?.code === "mfa_required") {
          setFactorRequired(true);
          setError("");
          return;
        }
        const issue = result.error?.issues?.[0]?.message;
        throw new Error(issue ?? result.error?.message ?? result.detail ?? "Authentication could not be completed.");
      }
      router.replace(firstAllowedPath(result as CurrentUser));
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-brand"><span className="brand-mark">P</span><span><strong>PolicyOS</strong><small>Assignment engine</small></span></div>
      <div className="auth-icon">{isSetup ? <ShieldCheck size={21} /> : <KeyRound size={21} />}</div>
      <p className="eyebrow">{isSetup ? "Secure initialization" : "Welcome back"}</p>
      <h1 id="auth-title">{isSetup ? "Create the Root account" : "Sign in to PolicyOS"}</h1>
      <p className="page-subtitle">{isSetup ? "This one-time account initializes the workspace and has full access during Phase 1." : "Use the account created for this PolicyOS workspace."}</p>
      {error && <div className="error-banner auth-message" role="alert"><CircleAlert size={14} />{error}</div>}
      <form className="auth-form" onSubmit={submit}>
        {isSetup && <label className="field"><span className="field-label">Full name</span><input className="input" required autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Priya Shah" /></label>}
        <label className="field"><span className="field-label">Email address</span><input className="input" required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
        <label className="field"><span className="field-label">Password</span><input className="input" required type="password" minLength={isSetup ? 12 : 1} maxLength={128} autoComplete={isSetup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {!isSetup && factorRequired && <><label className="field"><span className="field-label">{useRecovery ? "Recovery code" : "Authenticator code"}</span><input className="input" required inputMode={useRecovery ? "text" : "numeric"} autoComplete="one-time-code" value={factor} onChange={(event) => setFactor(event.target.value)} placeholder={useRecovery ? "xxxxxx-xxxxxx" : "000000"} /></label><button className="button secondary" type="button" onClick={() => { setUseRecovery((value) => !value); setFactor(""); }}>{useRecovery ? "Use authenticator code" : "Use a recovery code"}</button></>}
        {isSetup && <label className="field"><span className="field-label">Confirm password</span><input className="input" required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>}
        {isSetup && <div className="auth-requirement"><Check size={13} /> Use at least 12 characters. The password is stored only as a secure hash.</div>}
        <button className="button auth-submit" disabled={busy} type="submit">{busy ? "Please wait…" : isSetup ? "Create Root account" : "Sign in"}<ArrowRight size={14} /></button>
      </form>
      {!isSetup && <Link className="popover-footer" href="/recover">Forgot your password?</Link>}
      <div className="auth-security"><LockKeyhole size={13} /><span>{isSetup ? "Root setup closes permanently after this account is created." : "Your session is stored in a secure, HTTP-only cookie."}</span></div>
    </section>
  </main>;
}
