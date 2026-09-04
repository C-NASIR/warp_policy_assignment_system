"use client";

import Link from "next/link";
import { Check, CircleAlert, KeyRound } from "lucide-react";
import { FormEvent, useState } from "react";

export function RecoveryForm() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [factor, setFactor] = useState("");
  const [requested, setRequested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function requestReset(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch("/api/backend/auth/password-reset/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.message ?? "Recovery could not be started.");
      if (result.reset_token) setToken(result.reset_token);
      setRequested(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Recovery could not be started."); }
    finally { setBusy(false); }
  }

  async function finishReset(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmation) { setError("The new passwords do not match."); return; }
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/backend/auth/password-reset/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, new_password: password, ...(factor ? { recovery_code: factor } : {}) }) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.issues?.[0]?.message ?? result.error?.message ?? result.detail ?? "The password could not be reset.");
      setComplete(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The password could not be reset."); }
    finally { setBusy(false); }
  }

  return <main className="auth-page"><section className="auth-card" aria-labelledby="recovery-title"><div className="auth-brand"><span className="brand-mark">P</span><span><strong>PolicyOS</strong><small>Assignment engine</small></span></div><div className="auth-icon"><KeyRound size={21} /></div><p className="eyebrow">Account recovery</p><h1 id="recovery-title">Reset your password</h1><p className="page-subtitle">Recovery links are short-lived, single-use, and sign out every active device.</p>{error && <div className="error-banner auth-message" role="alert"><CircleAlert size={14} />{error}</div>}{complete ? <div className="success-banner" role="status"><Check size={14} />Password reset complete. <Link href="/login">Return to sign in</Link>.</div> : !requested ? <form className="auth-form" onSubmit={requestReset}><label className="field"><span className="field-label">Email address</span><input className="input" required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><button className="button auth-submit" disabled={busy} type="submit">{busy ? "Requesting…" : "Request recovery"}</button></form> : <form className="auth-form" onSubmit={finishReset}><div className="success-banner"><Check size={14} />If the account exists, recovery instructions have been generated.</div><label className="field"><span className="field-label">Recovery token</span><input className="input" required value={token} onChange={(event) => setToken(event.target.value)} /></label><label className="field"><span className="field-label">MFA recovery code (if enabled)</span><input className="input" value={factor} onChange={(event) => setFactor(event.target.value)} /></label><label className="field"><span className="field-label">New password</span><input className="input" required type="password" minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /></label><label className="field"><span className="field-label">Confirm password</span><input className="input" required type="password" minLength={12} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><button className="button auth-submit" disabled={busy} type="submit">{busy ? "Resetting…" : "Reset password"}</button></form>}<Link className="popover-footer" href="/login">Back to sign in</Link></section></main>;
}
