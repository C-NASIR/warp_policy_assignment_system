"use client";

import { CircleAlert, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { AuthFrame } from "@/components/features/auth";
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
          result.error_description ??
            result.error?.message ??
            "Authorization could not be completed.",
        );
      }
      window.location.assign(result.redirect_uri);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authorization could not be completed.");
      setBusy(false);
    }
  }

  return (
    <AuthFrame
      eyebrow="Connect an agent"
      title={<>Allow {request.client_name} to use PolicyOS?</>}
      titleId="authorization-title"
      description="The agent will act as you. PolicyOS will apply your current permissions, employee visibility, and assignment-field visibility to every request."
      icon={<LockKeyhole size={21} />}
      brandDetail="Agent access"
      contextLabel="User-bound authorization"
      contextTitle="Agent access never becomes an authorization shortcut."
      contextBody="The connected client receives only the access already granted to you. PolicyOS keeps validation, role checks, and audit behavior on the same trusted path."
      contextPoints={[
        "OAuth authorization code flow with PKCE",
        "Your current permissions apply to every request",
        "Passwords and MFA codes are never shared",
      ]}
    >
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
    </AuthFrame>
  );
}
