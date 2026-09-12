"use client";

import { Check, CircleAlert, KeyRound, Laptop, ShieldCheck, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { FormEvent, useState } from "react";
import { Badge, Button } from "@/components/ui";
import type { AccountSecurity } from "@/lib/types";
import styles from "./security-form.module.css";

type ErrorResult = {
  error?: { issues?: { message?: string }[]; message?: string };
  detail?: string;
};

function message(result: ErrorResult, fallback: string) {
  return result.error?.issues?.[0]?.message ?? result.error?.message ?? result.detail ?? fallback;
}

export function SecurityForm({ initialSecurity }: { initialSecurity: AccountSecurity }) {
  const router = useRouter();
  const [security, setSecurity] = useState(initialSecurity);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [mfaPassword, setMfaPassword] = useState("");
  const [mfaSecret, setMfaSecret] = useState("");
  const [mfaProvisioningUri, setMfaProvisioningUri] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [stepPassword, setStepPassword] = useState("");
  const [stepCode, setStepCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function call(path: string, method = "POST", body?: object) {
    const response = await fetch(`/api/backend${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new Error(message(result, "The security change could not be completed."));
    return result as ErrorResult & Record<string, unknown>;
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await call("/auth/change-password", "POST", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setNotice("Password changed. Other active sessions were signed out.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The password could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  async function startMfa(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await call("/auth/mfa/setup", "POST", { current_password: mfaPassword });
      setMfaSecret(String(result.secret));
      setMfaProvisioningUri(String(result.provisioning_uri));
      setNotice("Scan the QR code with your authenticator, then verify a code.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "MFA setup could not start.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmMfa(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await call("/auth/mfa/confirm", "POST", { code: mfaCode });
      setRecoveryCodes(result.recovery_codes as string[]);
      setSecurity((value) => ({ ...value, mfa_enabled: true }));
      setMfaSecret("");
      setMfaProvisioningUri("");
      setMfaCode("");
      setMfaPassword("");
      setNotice("MFA is enabled. Save the recovery codes now; they are shown only once.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The code could not be confirmed.");
    } finally {
      setBusy(false);
    }
  }

  async function disableMfa(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await call("/auth/mfa", "DELETE", { current_password: mfaPassword, mfa_code: mfaCode });
      setSecurity((value) => ({ ...value, mfa_enabled: false }));
      setMfaPassword("");
      setMfaCode("");
      setNotice("MFA was disabled and all previous sessions were revoked.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "MFA could not be disabled.");
    } finally {
      setBusy(false);
    }
  }

  async function stepUp(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await call("/auth/reauthenticate", "POST", {
        password: stepPassword,
        ...(stepCode ? { mfa_code: stepCode } : {}),
      });
      setStepPassword("");
      setStepCode("");
      setNotice("Identity verified. Sensitive actions are unlocked for 10 minutes.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Identity verification failed.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeOthers() {
    setBusy(true);
    setError("");
    try {
      await call("/auth/sessions/revoke-others");
      setSecurity((value) => ({
        ...value,
        sessions: value.sessions.filter((item) => item.current),
      }));
      setNotice("Every other device has been signed out.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sessions could not be revoked.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeAll() {
    setBusy(true);
    setError("");
    try {
      await call("/auth/sessions/revoke-all");
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  async function acknowledge(id: number) {
    try {
      const result = await call(`/auth/security-events/${id}/acknowledge`);
      setSecurity((value) => ({
        ...value,
        events: value.events.map((item) => (item.id === id ? (result as typeof item) : item)),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The event could not be acknowledged.");
    }
  }

  return (
    <div className="detail-grid">
      <div className="detail-main">
        {error && (
          <div className="error-banner" role="alert">
            <CircleAlert size={14} />
            {error}
          </div>
        )}
        {notice && (
          <div className="success-banner" role="status">
            <Check size={14} />
            {notice}
          </div>
        )}
        {security.mfa_required && !security.mfa_enabled && (
          <div className="error-banner" role="alert">
            <TriangleAlert size={14} />
            Root access requires MFA before privileged changes can be made.
          </div>
        )}
        <section className="panel security-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Multi-factor authentication</h2>
              <div className="panel-caption">
                Protect privileged access with a TOTP authenticator and one-time recovery codes.
              </div>
            </div>
            <Badge tone={security.mfa_enabled ? "success" : "warning"}>
              <ShieldCheck size={11} />
              {security.mfa_enabled ? "Enabled" : "Not enabled"}
            </Badge>
          </div>
          <div className="panel-body">
            {!security.mfa_enabled ? (
              !mfaSecret ? (
                <form className="security-form" onSubmit={startMfa}>
                  <label className="field">
                    <span className="field-label">Current password</span>
                    <input
                      className="input"
                      required
                      type="password"
                      autoComplete="current-password"
                      value={mfaPassword}
                      onChange={(event) => setMfaPassword(event.target.value)}
                    />
                  </label>
                  <Button disabled={busy} type="submit">
                    Set up authenticator
                  </Button>
                </form>
              ) : (
                <form className="security-form" onSubmit={confirmMfa}>
                  {mfaProvisioningUri && (
                    <div className="mfa-qr">
                      <QRCodeSVG
                        value={mfaProvisioningUri}
                        size={200}
                        level="M"
                        title="PolicyOS authenticator setup QR code"
                      />
                      <span>Scan with your authenticator app</span>
                    </div>
                  )}
                  <div className="auth-requirement">
                    Can&apos;t scan it? Enter this setup key manually: <strong>{mfaSecret}</strong>
                  </div>
                  <label className="field">
                    <span className="field-label">6-digit authenticator code</span>
                    <input
                      className="input"
                      required
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      value={mfaCode}
                      onChange={(event) => setMfaCode(event.target.value)}
                    />
                  </label>
                  <Button disabled={busy} type="submit">
                    Verify and enable
                  </Button>
                </form>
              )
            ) : (
              <form className="security-form" onSubmit={disableMfa}>
                <label className="field">
                  <span className="field-label">Current password</span>
                  <input
                    className="input"
                    required
                    type="password"
                    value={mfaPassword}
                    onChange={(event) => setMfaPassword(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field-label">Authenticator code</span>
                  <input
                    className="input"
                    required
                    inputMode="numeric"
                    value={mfaCode}
                    onChange={(event) => setMfaCode(event.target.value)}
                  />
                </label>
                <Button variant="danger" disabled={busy} type="submit">
                  Disable MFA
                </Button>
              </form>
            )}
            {recoveryCodes.length > 0 && (
              <div className="auth-requirement">
                <strong>Recovery codes</strong>
                <pre>{recoveryCodes.join("\n")}</pre>
              </div>
            )}
          </div>
        </section>
        <section className="panel security-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Password</h2>
              <div className="panel-caption">
                Changing your password signs out every other active session.
              </div>
            </div>
            <Badge tone="accent">
              <KeyRound size={11} />
              Protected
            </Badge>
          </div>
          <div className="panel-body">
            <form className="security-form" onSubmit={changePassword}>
              <label className="field">
                <span className="field-label">Current password</span>
                <input
                  className="input"
                  required
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">New password</span>
                <input
                  className="input"
                  required
                  type="password"
                  minLength={12}
                  maxLength={128}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Confirm new password</span>
                <input
                  className="input"
                  required
                  type="password"
                  minLength={12}
                  maxLength={128}
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
              </label>
              <Button disabled={busy} type="submit">
                Change password
              </Button>
            </form>
          </div>
        </section>
        <section className="panel security-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Confirm your identity</h2>
              <div className="panel-caption">
                Sensitive administrative actions require a recent password and MFA check.
              </div>
            </div>
          </div>
          <div className="panel-body">
            <form className="security-form" onSubmit={stepUp}>
              <label className="field">
                <span className="field-label">Password</span>
                <input
                  className="input"
                  required
                  type="password"
                  value={stepPassword}
                  onChange={(event) => setStepPassword(event.target.value)}
                />
              </label>
              {security.mfa_enabled && (
                <label className="field">
                  <span className="field-label">Authenticator code</span>
                  <input
                    className="input"
                    required
                    inputMode="numeric"
                    value={stepCode}
                    onChange={(event) => setStepCode(event.target.value)}
                  />
                </label>
              )}
              <Button disabled={busy} type="submit">
                Verify identity
              </Button>
            </form>
          </div>
        </section>
      </div>
      <aside className="detail-aside">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Active devices</h2>
              <div className="panel-caption">
                Sessions expire after inactivity and have a fixed lifetime.
              </div>
            </div>
            <Laptop size={16} />
          </div>
          <div className="panel-body">
            <div className="security-list">
              {security.sessions.map((item) => (
                <div className="security-list-item" key={item.id}>
                  <strong>
                    {item.current
                      ? "This device"
                      : item.user_agent?.split(" ").slice(0, 3).join(" ") || "Unknown device"}
                  </strong>
                  <small>
                    {item.last_ip || "Unknown address"} ·{" "}
                    {new Date(item.last_seen_at).toLocaleString()}
                  </small>
                </div>
              ))}
            </div>
            <div className="security-actions">
              <Button
                variant="secondary"
                disabled={busy || security.sessions.length < 2}
                onClick={revokeOthers}
              >
                Sign out others
              </Button>
              <Button variant="danger" disabled={busy} onClick={revokeAll}>
                Sign out all
              </Button>
            </div>
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Security events</h2>
              <div className="panel-caption">
                Review failed sign-ins, new addresses, and account changes.
              </div>
            </div>
          </div>
          <div className="panel-body">
            {security.events.length === 0 && (
              <p className="form-hint">No security events recorded.</p>
            )}
            <div className="security-list">
              {security.events.map((item) => (
                <div className="security-list-item" key={item.id}>
                  <strong>{item.event_type.replaceAll("_", " ")}</strong>
                  <small>
                    {new Date(item.created_at).toLocaleString()} · {item.severity}
                  </small>
                  {!item.acknowledged_at && item.severity !== "info" && (
                    <Button
                      className={styles.eventAction}
                      variant="secondary"
                      size="small"
                      onClick={() => acknowledge(item.id)}
                    >
                      Acknowledge
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      </aside>
    </div>
  );
}
