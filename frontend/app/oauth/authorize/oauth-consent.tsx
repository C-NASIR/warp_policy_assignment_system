"use client";

import { CircleAlert, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import type { OAuthAuthorizationRequest } from "@/lib/backend";

type AuthorizationParameters = OAuthAuthorizationRequest & {
  response_type: "code";
  code_challenge: string;
  code_challenge_method: "S256";
};

export function OAuthConsent({ request }: { request: AuthorizationParameters }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function decide(approve: boolean) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/backend/oauth/authorize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: request.client_id,
          redirect_uri: request.redirect_uri,
          response_type: request.response_type,
          code_challenge: request.code_challenge,
          code_challenge_method: request.code_challenge_method,
          scope: request.scope,
          state: request.state,
          resource: request.resource,
          approve,
        }),
      });
      const result = (await response.json().catch(() => ({}))) as {
        redirect_uri?: string;
        error_description?: string;
        error?: { message?: string };
      };
      if (!response.ok || !result.redirect_uri) {
        throw new Error(
          result.error_description ?? result.error?.message ?? "Authorization could not be completed.",
        );
      }
      window.location.assign(result.redirect_uri);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authorization could not be completed.");
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="authorization-title">
        <div className="auth-brand" aria-label="PolicyOS">
          <span className="brand-mark">P</span>
          <span>
            <strong>PolicyOS</strong>
            <small>Agent access</small>
          </span>
        </div>
        <p className="eyebrow">Connect an agent</p>
        <h1 id="authorization-title">Allow {request.client_name} to use PolicyOS?</h1>
        <p className="page-subtitle">
          The agent will act as you. PolicyOS will apply your current permissions, employee
          visibility, and assignment-field visibility to every request.
        </p>
        {error && (
          <div className="error-banner auth-message" role="alert">
            <CircleAlert size={14} />
            {error}
          </div>
        )}
        <div className="auth-security">
          <LockKeyhole size={13} />
          <span>Your password and MFA codes are never shared with the agent.</span>
        </div>
        <div className="auth-actions">
          <Button disabled={busy} fullWidth onClick={() => decide(true)}>
            {busy ? "Please wait…" : "Allow access"}
          </Button>
          <Button disabled={busy} fullWidth variant="secondary" onClick={() => decide(false)}>
            Deny
          </Button>
        </div>
      </section>
    </main>
  );
}
