"use client";

import { Archive, Check, CircleAlert, RotateCcw, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Policy } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

export function PolicyLifecycle({
  policy,
  apiConfigured,
}: {
  policy: Policy;
  apiConfigured: boolean;
}) {
  const router = useRouter();
  const [status, setStatus] = useState(policy.status);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useModalAccessibility(confirming, () => setConfirming(false));
  const nextStatus = status === "active" ? "archived" : "active";
  const canChangeStatus =
    status === "active" ? policy.capabilities.can_archive : policy.capabilities.can_activate;

  async function updateStatus() {
    setBusy(true);
    setError("");
    try {
      if (apiConfigured) {
        const response = await fetch(`/api/backend/policies/${policy.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: nextStatus }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok)
          throw new Error(
            result.error?.message ?? result.detail ?? "The policy status could not be changed.",
          );
      }
      setStatus(nextStatus);
      setConfirming(false);
      setNotice(
        nextStatus === "archived"
          ? "Policy archived and affected assignments reconciled."
          : "Policy reactivated and affected assignments reconciled.",
      );
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update the policy.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="heading-actions">
        <span
          className={`badge ${status === "active" ? "success" : status === "draft" ? "accent" : ""}`}
        >
          {status}
        </span>
        {canChangeStatus && (
          <button
            className="button secondary"
            onClick={() => {
              setConfirming(true);
              setNotice("");
            }}
            disabled={busy}
          >
            {status === "active" ? <Archive size={14} /> : <RotateCcw size={14} />}
            {status === "active" ? "Archive" : status === "draft" ? "Activate" : "Reactivate"}
          </button>
        )}
      </div>
      {(error || notice) && (
        <div
          className={error ? "floating-message error-banner" : "floating-message success-banner"}
          role={error ? "alert" : "status"}
        >
          {error ? <CircleAlert size={13} /> : <Check size={13} />}
          {error || notice}
        </div>
      )}
      {confirming && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirm-card"
            role="dialog"
            aria-modal="true"
            aria-label={`${nextStatus} policy`}
          >
            <button
              className="confirm-close"
              onClick={() => setConfirming(false)}
              aria-label="Close"
            >
              <X size={15} />
            </button>
            <div className="confirm-icon">
              {status === "active" ? <Archive size={18} /> : <RotateCcw size={18} />}
            </div>
            <h2>
              {status === "active" ? "Archive" : status === "draft" ? "Activate" : "Reactivate"}{" "}
              {policy.name}?
            </h2>
            <p>
              {status === "active"
                ? "This policy will stop participating in resolution. Employees will immediately fall back to other matching policies or no assignment."
                : "This policy will participate in resolution using its current version, and affected employees will be reconciled."}
            </p>
            <div className="heading-actions">
              <button className="button secondary" onClick={() => setConfirming(false)}>
                Cancel
              </button>
              <button className="button" disabled={busy} onClick={updateStatus}>
                {busy
                  ? "Applying…"
                  : `${status === "active" ? "Archive" : status === "draft" ? "Activate" : "Reactivate"} and reconcile`}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
