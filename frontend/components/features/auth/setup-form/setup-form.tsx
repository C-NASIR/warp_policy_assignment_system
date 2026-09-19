"use client";

import { ArrowRight, Check, CircleAlert, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type SubmitEvent, useState } from "react";
import { AuthFrame } from "@/components/features/auth/auth-frame/auth-frame";
import { Button, FormField, TextInput } from "@/components/ui";
import { firstAllowedPath } from "@/lib/permissions";
import type { CurrentUser } from "@/lib/types";

export function SetupForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/backend/auth/setup-root", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const result = (await response.json().catch(() => ({}))) as Partial<CurrentUser> & {
        error?: { issues?: { message?: string }[]; message?: string };
      };
      if (!response.ok) {
        throw new Error(
          result.error?.issues?.[0]?.message ??
            result.error?.message ??
            "Workspace setup could not be completed.",
        );
      }
      router.replace(firstAllowedPath(result as CurrentUser));
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Workspace setup could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame
      eyebrow="Workspace setup"
      title="Create the Root account"
      titleId="setup-title"
      description="Create the first administrator account to set up your workspace. You can add your team once you’re inside."
      icon={<ShieldCheck size={21} />}
      contextLabel="Start with accountable access"
      contextTitle="One trusted administrator starts the workspace."
      contextBody="The Root account establishes the first security boundary. Additional users and roles can be created after setup is complete."
      contextPoints={[
        "Root setup closes after the first account",
        "Passwords require at least 12 characters",
        "Roles and access can be delegated in-product",
      ]}
    >
      {error && (
        <div className="error-banner auth-message" role="alert">
          <CircleAlert size={14} />
          {error}
        </div>
      )}
      <form className="auth-form" onSubmit={submit}>
        <FormField label="Full name" htmlFor="setup-name" required>
          <TextInput
            id="setup-name"
            required
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Avery Chen"
          />
        </FormField>
        <FormField label="Email address" htmlFor="setup-email" required>
          <TextInput
            id="setup-email"
            required
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
          />
        </FormField>
        <FormField label="Password" htmlFor="setup-password" required>
          <TextInput
            id="setup-password"
            required
            type="password"
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FormField>
        <FormField label="Confirm password" htmlFor="setup-confirmation" required>
          <TextInput
            id="setup-confirmation"
            required
            type="password"
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
        </FormField>
        <div className="auth-requirement">
          <Check size={13} /> Use at least 12 characters. The password is stored only as a secure
          hash.
        </div>
        <Button className="auth-submit" disabled={busy} type="submit" fullWidth>
          {busy ? "Please wait…" : "Set up workspace"}
          <ArrowRight size={14} />
        </Button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
      <div className="auth-security">
        <LockKeyhole size={13} />
        <span>Root setup closes permanently after this account is created.</span>
      </div>
    </AuthFrame>
  );
}
