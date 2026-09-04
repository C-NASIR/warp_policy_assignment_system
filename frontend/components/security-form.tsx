"use client";

import { Check, CircleAlert, KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function SecurityForm() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch("/api/backend/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.issues?.[0]?.message ?? result.error?.message ?? result.detail ?? "The password could not be changed.");
      setCurrentPassword(""); setNewPassword(""); setConfirmation(""); setNotice("Password changed. Other active sessions were signed out."); router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The password could not be changed.");
    } finally { setBusy(false); }
  }

  return <section className="panel security-panel"><div className="panel-header"><div><h2 className="panel-title">Password</h2><div className="panel-caption">Changing your password signs out every other active session.</div></div><span className="badge accent"><KeyRound size={11} /> Protected</span></div><div className="panel-body">{error && <div className="error-banner" role="alert"><CircleAlert size={14} />{error}</div>}{notice && <div className="success-banner" role="status"><Check size={14} />{notice}</div>}<form className="security-form" onSubmit={submit}><label className="field"><span className="field-label">Current password</span><input className="input" required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label><label className="field"><span className="field-label">New password</span><input className="input" required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label><label className="field"><span className="field-label">Confirm new password</span><input className="input" required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><div className="form-footer security-footer"><span className="form-hint">Use at least 12 characters.</span><button className="button" disabled={busy} type="submit">{busy ? "Updating…" : "Change password"}</button></div></form></div></section>;
}
